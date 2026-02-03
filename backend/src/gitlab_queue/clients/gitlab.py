"""GitLab API client for Merge Queue Bot.

Provides async HTTP client for GitLab API with:
- Token-based authentication
- Rate limit handling with automatic backoff on 429
- Structured error handling and logging
- Automatic retries for transient failures

Example:
    >>> from gitlab_queue.config import load_settings
    >>> from gitlab_queue.clients.gitlab import GitLabClient
    >>> settings = load_settings()
    >>> async with GitLabClient(settings) as client:
    ...     mr = await client.get("/merge_requests/42")
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import httpx
from tenacity import (
    AsyncRetrying,
    RetryError,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from gitlab_queue.metrics import API_LATENCY, normalize_endpoint
from gitlab_queue.models.retorts import parse_job, parse_merge_request, parse_note, parse_pipeline
from gitlab_queue.utils.circuit_breaker import (
    CircuitBreaker,
    CircuitOpenError,
    create_circuit_breaker,
)
from gitlab_queue.utils.logging import get_logger
from gitlab_queue.utils.retry import log_after_retry, log_before_retry

if TYPE_CHECKING:
    from types import TracebackType

    from gitlab_queue.config import Settings
    from gitlab_queue.models.mr import MergeRequest, Note
    from gitlab_queue.models.pipeline import Job, Pipeline

log = get_logger(__name__)


# Keys that may contain sensitive data and should be redacted from response bodies
_SENSITIVE_KEYS = frozenset(
    {
        "token",
        "tokens",
        "access_token",
        "refresh_token",
        "private_token",
        "password",
        "secret",
        "api_key",
        "apikey",
        "auth",
        "authorization",
        "credential",
        "credentials",
        "key",
        "private_key",
        "secret_key",
    }
)


def _sanitize_response_body(body: dict[str, Any] | str | None) -> dict[str, Any] | str | None:
    """Sanitize response body by redacting sensitive keys.

    Recursively processes dicts to replace values of sensitive keys with '***'.
    This prevents accidental exposure of tokens/secrets in logs or error tracking.
    """
    if body is None or isinstance(body, str):
        return body

    def redact_dict(d: dict[str, Any]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in d.items():
            key_lower = key.lower()
            if any(sensitive in key_lower for sensitive in _SENSITIVE_KEYS):
                result[key] = "***"
            elif isinstance(value, dict):
                result[key] = redact_dict(value)
            elif isinstance(value, list):
                result[key] = [redact_dict(item) if isinstance(item, dict) else item for item in value]
            else:
                result[key] = value
        return result

    return redact_dict(body)


@dataclass
class RateLimitState:
    """Tracks GitLab API rate limit state.

    This dataclass stores the current rate limit information from GitLab API
    response headers and provides utility properties for adaptive throttling.

    Attributes:
        limit: Maximum requests allowed per window (RateLimit-Limit header).
        remaining: Requests remaining in current window (RateLimit-Remaining header).
        reset_at: Unix timestamp when limit resets (RateLimit-Reset header).
        last_updated: Monotonic time when state was last updated.
    """

    limit: int | None = None
    remaining: int | None = None
    reset_at: int | None = None
    last_updated: float = field(default_factory=time.monotonic)

    @property
    def usage_ratio(self) -> float | None:
        """Return ratio of used quota (0.0 to 1.0), or None if unknown.

        Returns:
            Float between 0.0 and 1.0 indicating usage (0.0 = none used, 1.0 = all used),
            or None if limit/remaining are not available.
        """
        if self.limit is None or self.remaining is None or self.limit == 0:
            return None
        return 1.0 - (self.remaining / self.limit)

    def _exceeds_threshold(self, threshold: float) -> bool:
        """Check if usage exceeds the given threshold.

        Args:
            threshold: Usage ratio threshold (0.0 to 1.0).

        Returns:
            True if usage ratio is known and exceeds threshold.
        """
        ratio = self.usage_ratio
        return ratio is not None and ratio > threshold

    def is_approaching_limit(self, threshold: float) -> bool:
        """Check if usage exceeds the warning threshold.

        Args:
            threshold: Usage ratio threshold (e.g., 0.8 for 80%).

        Returns:
            True if usage ratio is known and exceeds threshold.
        """
        return self._exceeds_threshold(threshold)

    def is_critical(self, threshold: float) -> bool:
        """Check if usage exceeds the critical threshold.

        Args:
            threshold: Critical usage ratio threshold (e.g., 0.95 for 95%).

        Returns:
            True if usage ratio is known and exceeds threshold.
        """
        return self._exceeds_threshold(threshold)

    @property
    def seconds_until_reset(self) -> float | None:
        """Seconds until rate limit resets, or None if unknown.

        Returns:
            Float seconds remaining, clamped to minimum 0.0,
            or None if reset_at is not available.
        """
        if self.reset_at is None:
            return None
        return max(0.0, self.reset_at - time.time())


class GitLabAPIError(Exception):
    """Base exception for GitLab API errors.

    Response body is automatically sanitized to remove sensitive data before storage.
    The __repr__ and __str__ methods never include the response body to prevent
    accidental exposure in logs or error tracking systems.
    """

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        response_body: dict[str, Any] | str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        # Sanitize response body before storing to remove sensitive data
        self._response_body = _sanitize_response_body(response_body)

    @property
    def response_body(self) -> dict[str, Any] | str | None:
        """Return sanitized response body."""
        return self._response_body

    def __repr__(self) -> str:
        """Safe representation that excludes response body."""
        return f"{self.__class__.__name__}({self.args[0]!r}, status_code={self.status_code})"

    def __str__(self) -> str:
        """Safe string representation."""
        if self.status_code:
            return f"{self.args[0]} (status: {self.status_code})"
        return str(self.args[0])


class GitLabNotFoundError(GitLabAPIError):
    """Raised when resource is not found (404)."""


class GitLabConflictError(GitLabAPIError):
    """Raised when there is a conflict (409), e.g., merge conflicts."""


class GitLabRateLimitError(GitLabAPIError):
    """Raised when rate limit is hit (429)."""

    def __init__(
        self,
        message: str,
        retry_after: int | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(message, **kwargs)
        self.retry_after = retry_after


class GitLabServerError(GitLabAPIError):
    """Raised for server errors (5xx)."""


class GitLabCircuitOpenError(GitLabAPIError):
    """Raised when circuit breaker is open and GitLab API requests are blocked.

    This indicates that GitLab has been experiencing repeated failures and
    the circuit breaker is protecting the system from cascading failures.

    Attributes:
        retry_after: Time in seconds until circuit may attempt recovery.
    """

    def __init__(
        self,
        message: str = "GitLab API circuit breaker is open",
        retry_after: float | None = None,
    ) -> None:
        super().__init__(message, status_code=None)
        self.retry_after = retry_after


class GitLabClient:
    """Async HTTP client for GitLab API.

    Handles authentication, rate limiting, and error responses.
    Should be used as async context manager for proper resource cleanup.

    Attributes:
        base_url: GitLab API base URL (e.g., https://gitlab.com/api/v4)
        project_id: GitLab project ID for API requests

    Example:
        Production usage (default transport):
            >>> client = GitLabClient(settings)

        Testing with MockTransport:
            >>> transport = httpx.MockTransport(handler)
            >>> client = GitLabClient(settings, transport=transport)
    """

    def __init__(
        self,
        settings: Settings,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        """Initialize GitLab client with settings.

        Args:
            settings: Application settings with GitLab configuration.
            transport: Optional custom transport for testing. If None, uses default.
        """
        self._settings = settings
        self._gitlab_url = settings.gitlab_url.rstrip("/")
        self._base_url = f"{self._gitlab_url}/api/v4"
        self._project_id = settings.gitlab_project_id
        self._max_retries = settings.api_max_retries

        # Get the actual token value for headers
        token = settings.gitlab_token.get_secret_value()

        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers={
                "Private-Token": token,
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            timeout=httpx.Timeout(30.0, connect=10.0),
            transport=transport,
        )

        # Initialize circuit breaker for API protection
        self._circuit_breaker = create_circuit_breaker(settings, name="gitlab_api")

        # Initialize rate limit tracking
        self._rate_limit_state = RateLimitState()
        self._rate_limit_lock = asyncio.Lock()

    @property
    def rate_limit_state(self) -> RateLimitState:
        """Return current rate limit state for inspection.

        The returned state is a snapshot and may be updated by concurrent requests.
        """
        return self._rate_limit_state

    @property
    def circuit_breaker(self) -> CircuitBreaker:
        """Return the circuit breaker for inspection/testing."""
        return self._circuit_breaker

    @property
    def base_url(self) -> str:
        """Return the GitLab API base URL."""
        return self._base_url

    @property
    def project_id(self) -> int:
        """Return the GitLab project ID."""
        return self._project_id

    async def __aenter__(self) -> GitLabClient:
        """Enter async context."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Exit async context and close HTTP client."""
        await self.close()

    async def close(self) -> None:
        """Close the HTTP client and release resources."""
        await self._client.aclose()

    def _project_path(self, path: str) -> str:
        """Build project-scoped API path.

        Args:
            path: API path relative to project (e.g., /merge_requests/42)

        Returns:
            Full API path including project prefix.

        Raises:
            ValueError: If path contains traversal sequences.
        """
        path = path.lstrip("/")
        # Prevent path traversal attacks
        if ".." in path:
            raise ValueError(f"Path traversal not allowed: {path}")
        return f"/projects/{self._project_id}/{path}"

    def _parse_rate_limit_headers(self, response: httpx.Response) -> tuple[int | None, int | None, int | None]:
        """Parse rate limit headers from GitLab response.

        Returns:
            Tuple of (limit, remaining, reset_timestamp)
        """
        limit = response.headers.get("RateLimit-Limit")
        remaining = response.headers.get("RateLimit-Remaining")
        reset = response.headers.get("RateLimit-Reset")

        return (
            int(limit) if limit else None,
            int(remaining) if remaining else None,
            int(reset) if reset else None,
        )

    def _parse_retry_after(self, response: httpx.Response) -> int | None:
        """Parse Retry-After header from 429 response."""
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                return int(retry_after)
            except ValueError:
                return None
        return None

    def _parse_response_body(self, response: httpx.Response) -> dict[str, Any] | str | None:
        """Try to parse response body as JSON, fallback to text."""
        try:
            body: dict[str, Any] = response.json()
            return body
        except Exception:
            text = response.text
            return text if text else None

    def _extract_error_message(self, body: dict[str, Any] | str | None, reason_phrase: str) -> str:
        """Extract error message from response body."""
        if isinstance(body, dict):
            return str(body.get("message") or body.get("error") or body)
        return body or reason_phrase

    def _raise_rate_limit_error(
        self, response: httpx.Response, body: dict[str, Any] | str | None, error_msg: str
    ) -> None:
        """Raise rate limit error with logging."""
        retry_after = self._parse_retry_after(response)
        limit, remaining, reset = self._parse_rate_limit_headers(response)

        log.warning(
            "Rate limit hit",
            retry_after=retry_after,
            rate_limit=limit,
            rate_remaining=remaining,
            rate_reset=reset,
        )

        raise GitLabRateLimitError(
            f"Rate limit exceeded: {error_msg}",
            status_code=429,
            response_body=body,
            retry_after=retry_after,
        )

    def _handle_error_response(self, response: httpx.Response) -> None:
        """Handle error responses and raise appropriate exceptions."""
        if response.is_success:
            return

        status_code = response.status_code
        body = self._parse_response_body(response)
        error_msg = self._extract_error_message(body, response.reason_phrase)

        log.warning(
            "GitLab API error",
            status_code=status_code,
            method=response.request.method,
            url=str(response.request.url),
            error=error_msg,
        )

        error_map: dict[int, tuple[type[GitLabAPIError], str]] = {
            404: (GitLabNotFoundError, "Resource not found"),
            409: (GitLabConflictError, "Conflict"),
        }

        if status_code in error_map:
            error_class, prefix = error_map[status_code]
            raise error_class(f"{prefix}: {error_msg}", status_code=status_code, response_body=body)

        if status_code == 429:
            self._raise_rate_limit_error(response, body, error_msg)

        if 500 <= status_code < 600:
            raise GitLabServerError(f"Server error: {error_msg}", status_code=status_code, response_body=body)

        raise GitLabAPIError(f"API error: {error_msg}", status_code=status_code, response_body=body)

    async def _handle_rate_limit(self, error: GitLabRateLimitError) -> None:
        """Wait for rate limit to reset.

        Args:
            error: Rate limit error with retry information.
        """
        wait_seconds = error.retry_after or 60  # Default 60s if no Retry-After
        wait_seconds = min(wait_seconds, 300)  # Cap at 5 minutes

        log.info("Waiting for rate limit reset", wait_seconds=wait_seconds)
        await asyncio.sleep(wait_seconds)

    async def _update_rate_limit_state(self, response: httpx.Response) -> None:
        """Update rate limit state from response headers.

        Called after every successful response to track current rate limit status.
        Logs proactively when approaching or at critical limit.

        Args:
            response: HTTP response containing rate limit headers.
        """
        limit, remaining, reset = self._parse_rate_limit_headers(response)

        # Skip if no rate limit headers present
        if limit is None and remaining is None:
            return

        async with self._rate_limit_lock:
            self._rate_limit_state = RateLimitState(
                limit=limit,
                remaining=remaining,
                reset_at=reset,
                last_updated=time.monotonic(),
            )

        # Log proactively based on thresholds
        state = self._rate_limit_state
        warning_threshold = self._settings.rate_limit_warning_threshold
        critical_threshold = self._settings.rate_limit_critical_threshold

        if state.is_critical(critical_threshold):
            log.warning(
                "Rate limit critical",
                limit=limit,
                remaining=remaining,
                reset_seconds=state.seconds_until_reset,
                usage_ratio=state.usage_ratio,
            )
        elif state.is_approaching_limit(warning_threshold):
            log.info(
                "Rate limit approaching",
                limit=limit,
                remaining=remaining,
                reset_seconds=state.seconds_until_reset,
                usage_ratio=state.usage_ratio,
            )

    async def _apply_rate_limit_throttle(self) -> None:
        """Apply adaptive throttling based on rate limit state.

        Implements linear scaling delay when approaching rate limit:
        - At warning threshold (80%): base delay
        - At 100%: 5x base delay

        Does NOT block event loop - uses asyncio.sleep.
        """
        state = self._rate_limit_state
        ratio = state.usage_ratio
        warning_threshold = self._settings.rate_limit_warning_threshold

        if ratio is None or ratio <= warning_threshold:
            return  # No throttling needed

        # Linear scaling: at threshold = base delay, at 100% = 5x base delay
        # scale goes from 0.0 (at threshold) to 1.0 (at 100%)
        scale = (ratio - warning_threshold) / (1.0 - warning_threshold)
        delay = self._settings.rate_limit_throttle_delay_seconds * (1 + 4 * scale)

        # Cap delay at time until reset if available and shorter
        reset_seconds = state.seconds_until_reset
        if reset_seconds is not None and reset_seconds < delay:
            delay = reset_seconds

        log.debug(
            "Rate limit throttling",
            delay_seconds=round(delay, 2),
            usage_ratio=round(ratio, 3),
        )

        await asyncio.sleep(delay)

    async def _request(
        self,
        method: str,
        path: str,
        *,
        project_scoped: bool = True,
        **kwargs: Any,
    ) -> httpx.Response:
        """Make HTTP request with circuit breaker, rate limiting, and retry logic.

        Request flow:
        1. Circuit breaker check (fail fast if open)
        2. Adaptive rate limit throttling (slow down when approaching limit)
        3. Tenacity retry loop (handles transient errors)
        4. HTTP request execution
        5. Update rate limit state from response headers

        Args:
            method: HTTP method (GET, POST, PUT, DELETE).
            path: API path (will be project-scoped if project_scoped=True).
            project_scoped: Whether to prefix path with /projects/{id}/.
            **kwargs: Additional arguments passed to httpx.

        Returns:
            HTTP response.

        Raises:
            GitLabCircuitOpenError: If circuit breaker is open.
            GitLabAPIError: On API errors after retries exhausted.
        """
        full_path = self._project_path(path) if project_scoped else path.lstrip("/")

        log.debug(
            "GitLab API request",
            method=method,
            path=full_path,
        )

        await self._check_circuit_breaker(method, full_path)
        await self._apply_rate_limit_throttle()

        normalized_path = normalize_endpoint(full_path)

        try:
            return await self._execute_with_retry(method, full_path, normalized_path, **kwargs)
        except RetryError as e:
            last_exc = e.last_attempt.exception()
            if last_exc is not None:
                await self._circuit_breaker.record_failure(last_exc)
                raise last_exc from e
            raise GitLabAPIError("Request failed after retries") from e

    async def _check_circuit_breaker(self, method: str, path: str) -> None:
        """Check circuit breaker state before request."""
        try:
            await self._circuit_breaker.before_call()
        except CircuitOpenError as e:
            log.warning(
                "Request blocked by circuit breaker",
                method=method,
                path=path,
                retry_after=e.retry_after,
            )
            raise GitLabCircuitOpenError(
                f"GitLab API unavailable: {e}",
                retry_after=e.retry_after,
            ) from e

    async def _execute_with_retry(
        self,
        method: str,
        full_path: str,
        normalized_path: str,
        **kwargs: Any,
    ) -> httpx.Response:
        """Execute HTTP request with retry logic."""
        async for attempt in AsyncRetrying(
            retry=retry_if_exception_type((GitLabServerError, GitLabRateLimitError)),
            stop=stop_after_attempt(self._max_retries),
            wait=wait_exponential_jitter(initial=1, max=30, jitter=5),
            before_sleep=log_before_retry,
            after=log_after_retry,
            reraise=True,
        ):
            with attempt:
                response = await self._execute_single_request(method, full_path, normalized_path, **kwargs)
                return response

        raise AssertionError("Unreachable: retry loop completed without return or exception")

    async def _execute_single_request(
        self,
        method: str,
        full_path: str,
        normalized_path: str,
        **kwargs: Any,
    ) -> httpx.Response:
        """Execute a single HTTP request with metrics."""
        start_time = time.monotonic()
        try:
            response = await self._client.request(method, full_path, **kwargs)
        finally:
            duration = time.monotonic() - start_time
            API_LATENCY.labels(method=method, endpoint=normalized_path).observe(duration)

        await self._update_rate_limit_state(response)

        try:
            self._handle_error_response(response)
        except GitLabRateLimitError as e:
            await self._handle_rate_limit(e)
            raise

        await self._circuit_breaker.record_success()
        return response

    async def get(
        self,
        path: str,
        *,
        project_scoped: bool = True,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make GET request to GitLab API.

        Args:
            path: API path (e.g., /merge_requests/42).
            project_scoped: Whether to prefix with /projects/{id}/.
            params: Query parameters.

        Returns:
            Parsed JSON response.
        """
        response = await self._request("GET", path, project_scoped=project_scoped, params=params)
        result: dict[str, Any] = response.json()
        return result

    async def get_list(
        self,
        path: str,
        *,
        project_scoped: bool = True,
        params: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Make GET request expecting a list response.

        Args:
            path: API path (e.g., /merge_requests).
            project_scoped: Whether to prefix with /projects/{id}/.
            params: Query parameters.

        Returns:
            Parsed JSON list response.
        """
        response = await self._request("GET", path, project_scoped=project_scoped, params=params)
        result: list[dict[str, Any]] = response.json()
        return result

    async def post(
        self,
        path: str,
        *,
        project_scoped: bool = True,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make POST request to GitLab API.

        Args:
            path: API path.
            project_scoped: Whether to prefix with /projects/{id}/.
            json: JSON body.
            params: Query parameters.

        Returns:
            Parsed JSON response.
        """
        response = await self._request("POST", path, project_scoped=project_scoped, json=json, params=params)
        result: dict[str, Any] = response.json()
        return result

    async def put(
        self,
        path: str,
        *,
        project_scoped: bool = True,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make PUT request to GitLab API.

        Args:
            path: API path.
            project_scoped: Whether to prefix with /projects/{id}/.
            json: JSON body.
            params: Query parameters.

        Returns:
            Parsed JSON response.
        """
        response = await self._request("PUT", path, project_scoped=project_scoped, json=json, params=params)
        result: dict[str, Any] = response.json()
        return result

    async def delete(
        self,
        path: str,
        *,
        project_scoped: bool = True,
        params: dict[str, Any] | None = None,
    ) -> None:
        """Make DELETE request to GitLab API.

        Args:
            path: API path.
            project_scoped: Whether to prefix with /projects/{id}/.
            params: Query parameters.
        """
        await self._request("DELETE", path, project_scoped=project_scoped, params=params)

    # =========================================================================
    # Merge Request Operations (Task 6)
    # =========================================================================

    async def get_mr(self, iid: int) -> MergeRequest:
        """Get a merge request by its IID.

        Args:
            iid: Internal ID (project-scoped MR number).

        Returns:
            MergeRequest model with current MR data.

        Raises:
            GitLabNotFoundError: If MR with given IID does not exist.
            GitLabAPIError: On other API errors.
        """
        log.debug("Fetching merge request", mr_iid=iid)
        data = await self.get(f"/merge_requests/{iid}")
        mr = parse_merge_request(data)
        log.debug(
            "Fetched merge request",
            mr_iid=mr.iid,
            state=mr.state,
            merge_status=mr.merge_status,
        )
        return mr

    async def list_mrs_with_label(
        self,
        label: str,
        *,
        state: str = "opened",
    ) -> list[MergeRequest]:
        """List merge requests with a specific label.

        Args:
            label: Label name to filter by.
            state: MR state filter (opened, closed, merged, all).
                Defaults to "opened".

        Returns:
            List of MergeRequest models matching the criteria.

        Raises:
            GitLabAPIError: On API errors.
        """
        log.debug("Listing merge requests with label", label=label, state=state)
        data = await self.get_list(
            "/merge_requests",
            params={
                "labels": label,
                "state": state,
                "per_page": 100,  # Max allowed by GitLab
            },
        )
        mrs = [parse_merge_request(mr_data) for mr_data in data]
        log.debug(
            "Found merge requests with label",
            label=label,
            count=len(mrs),
        )
        return mrs

    async def rebase_mr(self, iid: int) -> bool:
        """Initiate a rebase operation for a merge request.

        This is an async operation - it returns immediately and the rebase
        runs in the background. Use check_rebase_status() to monitor progress.

        Args:
            iid: Internal ID of the merge request to rebase.

        Returns:
            True if rebase was initiated successfully.

        Raises:
            GitLabNotFoundError: If MR does not exist.
            GitLabConflictError: If MR has conflicts that prevent rebase.
            GitLabAPIError: On other API errors.
        """
        log.info("Initiating rebase", mr_iid=iid)
        try:
            await self.put(f"/merge_requests/{iid}/rebase")
            log.info("Rebase initiated successfully", mr_iid=iid)
            return True
        except GitLabConflictError:
            log.warning("Rebase failed due to conflicts", mr_iid=iid)
            raise

    async def check_rebase_status(self, iid: int) -> tuple[bool, bool]:
        """Check the status of a rebase operation.

        Args:
            iid: Internal ID of the merge request.

        Returns:
            Tuple of (rebase_in_progress, has_conflicts).
            - rebase_in_progress: True if rebase is still running.
            - has_conflicts: True if merge conflicts were detected.

        Raises:
            GitLabNotFoundError: If MR does not exist.
            GitLabAPIError: On other API errors.
        """
        log.debug("Checking rebase status", mr_iid=iid)
        mr = await self.get_mr(iid)
        log.debug(
            "Rebase status",
            mr_iid=iid,
            rebase_in_progress=mr.rebase_in_progress,
            has_conflicts=mr.has_conflicts,
        )
        return mr.rebase_in_progress, mr.has_conflicts

    async def get_mr_conflicts(self, iid: int) -> list[str]:
        """Get list of conflicted files for a merge request.

        Uses GitLab's internal /conflicts endpoint to fetch the list of files
        with merge conflicts. This endpoint is used by the GitLab web UI.

        Returns empty list if endpoint fails or MR has no conflicts
        (non-breaking fallback).

        Args:
            iid: Internal ID of the merge request.

        Returns:
            List of file paths with conflicts, or empty list on failure.
        """
        log.debug("Fetching conflict files", mr_iid=iid)
        try:
            data = await self.get_list(f"/merge_requests/{iid}/conflicts")
            # Each conflict entry has 'old_path' and 'new_path' fields
            files: list[str] = []
            for conflict in data:
                # Prefer new_path, fall back to old_path
                path = conflict.get("new_path") or conflict.get("old_path")
                if path:
                    files.append(path)
            log.debug("Found conflicted files", mr_iid=iid, count=len(files), files=files)
            return files
        except GitLabAPIError as e:
            log.debug("Could not fetch conflict files", mr_iid=iid, error=str(e))
            return []

    # =========================================================================
    # Pipeline Operations (Task 7)
    # =========================================================================

    async def get_mr_pipelines(self, iid: int) -> list[Pipeline]:
        """Get all pipelines for a merge request.

        Args:
            iid: Internal ID of the merge request.

        Returns:
            List of Pipeline models, ordered by creation date (newest first).

        Raises:
            GitLabNotFoundError: If MR does not exist.
            GitLabAPIError: On other API errors.
        """
        log.debug("Fetching pipelines for MR", mr_iid=iid)
        data = await self.get_list(f"/merge_requests/{iid}/pipelines")
        pipelines = [parse_pipeline(p) for p in data]
        log.debug(
            "Fetched pipelines for MR",
            mr_iid=iid,
            count=len(pipelines),
        )
        return pipelines

    async def get_latest_mr_pipeline(self, iid: int) -> Pipeline | None:
        """Get the latest pipeline for a merge request.

        Convenience method that returns only the most recent pipeline.

        Args:
            iid: Internal ID of the merge request.

        Returns:
            Latest Pipeline or None if no pipelines exist.

        Raises:
            GitLabNotFoundError: If MR does not exist.
            GitLabAPIError: On other API errors.
        """
        pipelines = await self.get_mr_pipelines(iid)
        if not pipelines:
            log.debug("No pipelines found for MR", mr_iid=iid)
            return None
        # First pipeline is the latest (API returns newest first)
        latest = pipelines[0]
        log.debug(
            "Latest pipeline for MR",
            mr_iid=iid,
            pipeline_id=latest.id,
            status=latest.status,
        )
        return latest

    async def get_pipeline_status(self, pipeline_id: int) -> Pipeline:
        """Get a pipeline by its ID.

        Args:
            pipeline_id: Pipeline ID.

        Returns:
            Pipeline model with current status.

        Raises:
            GitLabNotFoundError: If pipeline does not exist.
            GitLabAPIError: On other API errors.
        """
        log.debug("Fetching pipeline", pipeline_id=pipeline_id)
        data = await self.get(f"/pipelines/{pipeline_id}")
        pipeline = parse_pipeline(data)
        log.debug(
            "Fetched pipeline",
            pipeline_id=pipeline.id,
            status=pipeline.status,
        )
        return pipeline

    async def retry_pipeline_job(self, job_id: int) -> Job:
        """Retry a failed or canceled job.

        Args:
            job_id: Job ID to retry.

        Returns:
            Job model with updated status.

        Raises:
            GitLabNotFoundError: If job does not exist.
            GitLabAPIError: On other API errors (e.g., job cannot be retried).
        """
        log.info("Retrying job", job_id=job_id)
        data = await self.post(f"/jobs/{job_id}/retry")
        job = parse_job(data)
        log.info(
            "Job retry initiated",
            job_id=job.id,
            name=job.name,
            status=job.status,
        )
        return job

    async def create_pipeline(self, ref: str) -> Pipeline:
        """Create a new pipeline for the specified ref (branch).

        Fallback when GitLab doesn't auto-create pipeline after rebase.

        Args:
            ref: Branch name or commit SHA to create pipeline for.

        Returns:
            Pipeline model with the created pipeline details.

        Raises:
            GitLabAPIError: On API errors (e.g., no CI config, invalid ref).
            GitLabNotFoundError: If branch/ref doesn't exist.
        """
        log.info("Creating pipeline", ref=ref)
        data = await self.post("/pipelines", json={"ref": ref})
        pipeline = parse_pipeline(data)
        log.info("Pipeline created", pipeline_id=pipeline.id, ref=ref)
        return pipeline

    async def cancel_pipeline(self, pipeline_id: int) -> Pipeline:
        """Cancel a running pipeline.

        GitLab API: POST /projects/:id/pipelines/:pipeline_id/cancel

        Args:
            pipeline_id: Pipeline ID to cancel.

        Returns:
            Pipeline model with updated status (typically "canceled").

        Raises:
            GitLabNotFoundError: If pipeline does not exist.
            GitLabAPIError: On other API errors (e.g., pipeline already finished).
        """
        log.info("Cancelling pipeline", pipeline_id=pipeline_id)
        data = await self.post(f"/pipelines/{pipeline_id}/cancel")
        pipeline = parse_pipeline(data)
        log.info("Pipeline cancelled", pipeline_id=pipeline.id, status=pipeline.status)
        return pipeline

    async def get_pipeline_jobs(self, pipeline_id: int) -> list[Job]:
        """Get all jobs for a pipeline.

        Args:
            pipeline_id: Pipeline ID to fetch jobs for.

        Returns:
            List of Job objects for the pipeline.

        Raises:
            GitLabNotFoundError: If pipeline does not exist.
            GitLabAPIError: On other API errors.
        """
        log.debug("Fetching jobs for pipeline", pipeline_id=pipeline_id)
        data = await self.get_list(f"/pipelines/{pipeline_id}/jobs")
        jobs = [parse_job(job) for job in data]
        log.debug(
            "Fetched pipeline jobs",
            pipeline_id=pipeline_id,
            job_count=len(jobs),
        )
        return jobs

    # =========================================================================
    # Merge & Comment Operations (Task 8)
    # =========================================================================

    # Bot comment signature marker (invisible in rendered markdown)
    BOT_COMMENT_SIGNATURE = "<!-- merge-queue-bot -->"

    async def merge_mr(self, iid: int) -> MergeRequest:
        """Merge a merge request using fast-forward strategy.

        Checks merge_status before attempting merge to ensure MR is ready.
        If merge_status is 'checking' (GitLab recalculating after rebase),
        waits and retries up to max_retries times.

        Args:
            iid: Internal ID of the merge request to merge.

        Returns:
            MergeRequest model with updated state (should be 'merged').

        Raises:
            GitLabNotFoundError: If MR does not exist.
            GitLabConflictError: If MR cannot be merged (conflicts, not ready, timeout).
            GitLabAPIError: On other API errors.
        """
        log.info("Attempting to merge MR", mr_iid=iid)

        max_retries = self._settings.merge_status_retry_max
        retry_delay = self._settings.merge_status_retry_delay_seconds

        for attempt in range(max_retries):
            mr = await self.get_mr(iid)

            if mr.merge_status == "checking":
                log.info(
                    "Waiting for merge status check",
                    mr_iid=iid,
                    attempt=attempt + 1,
                    max_retries=max_retries,
                )
                await asyncio.sleep(retry_delay)
                continue

            if mr.merge_status == "can_be_merged":
                # Proceed with merge
                try:
                    data = await self.put(
                        f"/merge_requests/{iid}/merge",
                        json={"merge_method": "ff"},  # Fast-forward merge
                    )
                    merged_mr = parse_merge_request(data)
                    log.info(
                        "MR merged successfully",
                        mr_iid=merged_mr.iid,
                        state=merged_mr.state,
                    )
                    return merged_mr
                except GitLabAPIError as e:
                    # HTTP 422 "Branch cannot be merged" may be temporary after rebase
                    if e.status_code == 422 and not mr.has_conflicts:
                        log.info(
                            "Merge API returned 422, retrying",
                            mr_iid=iid,
                            attempt=attempt + 1,
                            error=str(e),
                        )
                        await asyncio.sleep(retry_delay)
                        continue
                    log.exception("Failed to merge MR", mr_iid=iid)
                    raise

            # Any other status is a real error
            log.warning(
                "MR not ready for merge",
                mr_iid=iid,
                merge_status=mr.merge_status,
                has_conflicts=mr.has_conflicts,
            )
            raise GitLabConflictError(
                f"MR !{iid} cannot be merged: status is '{mr.merge_status}'",
                status_code=409,
            )

        # Timeout after all retries
        log.warning(
            "Merge status check timeout",
            mr_iid=iid,
            merge_status="checking",
            attempts=max_retries,
        )
        raise GitLabConflictError(
            f"MR !{iid} merge status check timeout (status: 'checking')",
            status_code=409,
        )

    async def add_comment(self, iid: int, body: str) -> Note:
        """Add a comment to a merge request.

        Args:
            iid: Internal ID of the merge request.
            body: Comment body (supports markdown).

        Returns:
            Note model with the created comment.

        Raises:
            GitLabNotFoundError: If MR does not exist.
            GitLabAPIError: On other API errors.
        """
        log.debug("Adding comment to MR", mr_iid=iid)
        data = await self.post(
            f"/merge_requests/{iid}/notes",
            json={"body": body},
        )
        note = parse_note(data)
        log.debug("Comment added", mr_iid=iid, note_id=note.id)
        return note

    async def update_comment(self, iid: int, note_id: int, body: str) -> Note:
        """Update an existing comment on a merge request.

        Args:
            iid: Internal ID of the merge request.
            note_id: ID of the note/comment to update.
            body: New comment body (supports markdown).

        Returns:
            Note model with the updated comment.

        Raises:
            GitLabNotFoundError: If MR or note does not exist.
            GitLabAPIError: On other API errors.
        """
        log.debug("Updating comment", mr_iid=iid, note_id=note_id)
        data = await self.put(
            f"/merge_requests/{iid}/notes/{note_id}",
            json={"body": body},
        )
        note = parse_note(data)
        log.debug("Comment updated", mr_iid=iid, note_id=note.id)
        return note

    async def _find_bot_comment(self, iid: int) -> Note | None:
        """Find existing bot comment by signature marker.

        Searches through MR notes for a comment containing the bot signature.

        Args:
            iid: Internal ID of the merge request.

        Returns:
            Note if bot comment exists, None otherwise.
        """
        log.debug("Searching for bot comment", mr_iid=iid)
        notes_data = await self.get_list(f"/merge_requests/{iid}/notes")
        for note_data in notes_data:
            note = parse_note(note_data)
            if self.BOT_COMMENT_SIGNATURE in note.body and not note.system:
                log.debug("Found bot comment", mr_iid=iid, note_id=note.id)
                return note
        log.debug("No bot comment found", mr_iid=iid)
        return None

    async def add_or_update_pinned_comment(self, iid: int, body: str) -> Note:
        """Add or update a single pinned bot comment on a merge request.

        Uses a signature marker to identify the bot's comment. If a comment
        with the marker exists, it is updated. Otherwise, a new comment is
        created with the marker prepended.

        This ensures only one bot comment exists per MR (pinned comment pattern).

        Args:
            iid: Internal ID of the merge request.
            body: Comment body (supports markdown). Signature will be added.

        Returns:
            Note model with the created or updated comment.

        Raises:
            GitLabNotFoundError: If MR does not exist.
            GitLabAPIError: On other API errors.
        """
        # Ensure body includes the signature marker
        if self.BOT_COMMENT_SIGNATURE not in body:
            body = f"{self.BOT_COMMENT_SIGNATURE}\n{body}"

        existing_note = await self._find_bot_comment(iid)
        if existing_note:
            log.info("Updating existing bot comment", mr_iid=iid, note_id=existing_note.id)
            return await self.update_comment(iid, existing_note.id, body)

        log.info("Creating new bot comment", mr_iid=iid)
        return await self.add_comment(iid, body)

    async def remove_mr_label(self, iid: int, label: str) -> MergeRequest:
        """Remove a label from a merge request.

        Args:
            iid: Internal ID of the merge request.
            label: Label name to remove.

        Returns:
            Updated MergeRequest model.

        Raises:
            GitLabNotFoundError: If MR does not exist.
            GitLabAPIError: On other API errors.
        """
        log.info("Removing label from MR", mr_iid=iid, label=label)

        data = await self.put(
            f"merge_requests/{iid}",
            json={"remove_labels": label},
        )

        return parse_merge_request(data)


__all__: list[str] = [
    "GitLabAPIError",
    "GitLabCircuitOpenError",
    "GitLabClient",
    "GitLabConflictError",
    "GitLabNotFoundError",
    "GitLabRateLimitError",
    "GitLabServerError",
    "RateLimitState",
]
