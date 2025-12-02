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
from typing import TYPE_CHECKING, Any

import httpx
from tenacity import (
    AsyncRetrying,
    RetryError,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from gitlab_queue.utils.logging import get_logger

if TYPE_CHECKING:
    from types import TracebackType

    from gitlab_queue.config import Settings

log = get_logger(__name__)


# Keys that may contain sensitive data and should be redacted from response bodies
_SENSITIVE_KEYS = frozenset({
    "token", "tokens", "access_token", "refresh_token", "private_token",
    "password", "secret", "api_key", "apikey", "auth", "authorization",
    "credential", "credentials", "key", "private_key", "secret_key",
})


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
                result[key] = [
                    redact_dict(item) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                result[key] = value
        return result

    return redact_dict(body)


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


class GitLabClient:
    """Async HTTP client for GitLab API.

    Handles authentication, rate limiting, and error responses.
    Should be used as async context manager for proper resource cleanup.

    Attributes:
        base_url: GitLab API base URL (e.g., https://gitlab.com/api/v4)
        project_id: GitLab project ID for API requests
    """

    def __init__(self, settings: Settings) -> None:
        """Initialize GitLab client with settings.

        Args:
            settings: Application settings with GitLab configuration.
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
        )

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

    def _parse_rate_limit_headers(
        self, response: httpx.Response
    ) -> tuple[int | None, int | None, int | None]:
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

    def _parse_response_body(
        self, response: httpx.Response
    ) -> dict[str, Any] | str | None:
        """Try to parse response body as JSON, fallback to text."""
        try:
            body: dict[str, Any] = response.json()
            return body
        except Exception:
            text = response.text
            return text if text else None

    def _handle_error_response(self, response: httpx.Response) -> None:
        """Handle error responses and raise appropriate exceptions.

        Args:
            response: HTTP response to check.

        Raises:
            GitLabNotFoundError: For 404 responses.
            GitLabConflictError: For 409 responses.
            GitLabRateLimitError: For 429 responses.
            GitLabServerError: For 5xx responses.
            GitLabAPIError: For other 4xx responses.
        """
        if response.is_success:
            return

        status_code = response.status_code
        body = self._parse_response_body(response)
        method = response.request.method
        url = str(response.request.url)

        # Extract error message from body if available
        if isinstance(body, dict):
            error_msg = body.get("message") or body.get("error") or str(body)
        else:
            error_msg = body or response.reason_phrase

        log.warning(
            "GitLab API error",
            status_code=status_code,
            method=method,
            url=url,
            error=error_msg,
        )

        if status_code == 404:
            raise GitLabNotFoundError(
                f"Resource not found: {error_msg}",
                status_code=status_code,
                response_body=body,
            )

        if status_code == 409:
            raise GitLabConflictError(
                f"Conflict: {error_msg}",
                status_code=status_code,
                response_body=body,
            )

        if status_code == 429:
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
                status_code=status_code,
                response_body=body,
                retry_after=retry_after,
            )

        if 500 <= status_code < 600:
            raise GitLabServerError(
                f"Server error: {error_msg}",
                status_code=status_code,
                response_body=body,
            )

        # Other 4xx errors
        raise GitLabAPIError(
            f"API error: {error_msg}",
            status_code=status_code,
            response_body=body,
        )

    async def _handle_rate_limit(self, error: GitLabRateLimitError) -> None:
        """Wait for rate limit to reset.

        Args:
            error: Rate limit error with retry information.
        """
        wait_seconds = error.retry_after or 60  # Default 60s if no Retry-After
        wait_seconds = min(wait_seconds, 300)  # Cap at 5 minutes

        log.info("Waiting for rate limit reset", wait_seconds=wait_seconds)
        await asyncio.sleep(wait_seconds)

    async def _request(
        self,
        method: str,
        path: str,
        *,
        project_scoped: bool = True,
        **kwargs: Any,
    ) -> httpx.Response:
        """Make HTTP request with retry logic for transient failures.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE).
            path: API path (will be project-scoped if project_scoped=True).
            project_scoped: Whether to prefix path with /projects/{id}/.
            **kwargs: Additional arguments passed to httpx.

        Returns:
            HTTP response.

        Raises:
            GitLabAPIError: On API errors after retries exhausted.
        """
        full_path = self._project_path(path) if project_scoped else path.lstrip("/")

        log.debug(
            "GitLab API request",
            method=method,
            path=full_path,
        )

        try:
            async for attempt in AsyncRetrying(
                retry=retry_if_exception_type((GitLabServerError, GitLabRateLimitError)),
                stop=stop_after_attempt(self._max_retries),
                wait=wait_exponential_jitter(initial=1, max=30, jitter=5),
                reraise=True,
            ):
                with attempt:
                    try:
                        response = await self._client.request(method, full_path, **kwargs)
                        self._handle_error_response(response)
                        return response
                    except GitLabRateLimitError as e:
                        await self._handle_rate_limit(e)
                        raise
        except RetryError as e:
            # Re-raise the last exception from retries
            last_exc = e.last_attempt.exception()
            if last_exc is not None:
                raise last_exc from e
            raise GitLabAPIError("Request failed after retries") from e

        # This should never be reached, but needed for type checker
        msg = "Unexpected code path in _request"
        raise RuntimeError(msg)

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
        response = await self._request(
            "GET", path, project_scoped=project_scoped, params=params
        )
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
        response = await self._request(
            "GET", path, project_scoped=project_scoped, params=params
        )
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
        response = await self._request(
            "POST", path, project_scoped=project_scoped, json=json, params=params
        )
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
        response = await self._request(
            "PUT", path, project_scoped=project_scoped, json=json, params=params
        )
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
        await self._request(
            "DELETE", path, project_scoped=project_scoped, params=params
        )


__all__: list[str] = [
    "GitLabAPIError",
    "GitLabClient",
    "GitLabConflictError",
    "GitLabNotFoundError",
    "GitLabRateLimitError",
    "GitLabServerError",
]
