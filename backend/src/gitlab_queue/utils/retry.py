"""Retry utilities for GitLab Queue Bot.

Provides configurable retry decorators for:
- GitLab API calls (with rate limit handling)
- SQLite database operations (with lock handling)
- Rebase operations (with timeout support)

All decorators use tenacity for robust retry logic with:
- Exponential backoff with jitter
- Configurable max wait times
- Structured logging via structlog
- Exception-type filtering

Example:
    >>> from gitlab_queue.utils.retry import retry_gitlab_api
    >>> @retry_gitlab_api(max_retries=5)
    ... async def fetch_data(client):
    ...     return await client.get("/data")
"""

from __future__ import annotations

import sqlite3
from collections.abc import Awaitable, Callable, Coroutine  # noqa: TC003
from functools import wraps
from typing import Any, ParamSpec, TypeVar

from sqlalchemy.exc import IntegrityError, OperationalError
from tenacity import (
    AsyncRetrying,
    RetryCallState,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential_jitter,
)

from gitlab_queue.utils.logging import get_logger

P = ParamSpec("P")
T = TypeVar("T")

log = get_logger(__name__)


# =============================================================================
# Logging Callbacks for Tenacity
# =============================================================================


def log_before_retry(retry_state: RetryCallState) -> None:
    """Log before each retry attempt.

    Called by tenacity before sleeping between retries.
    Logs attempt number, exception type, and wait time.

    Args:
        retry_state: Tenacity's retry state with attempt info.
    """
    exception = retry_state.outcome.exception() if retry_state.outcome else None
    wait_time = retry_state.next_action.sleep if retry_state.next_action else None

    elapsed = retry_state.seconds_since_start
    log.warning(
        "Retrying operation",
        attempt=retry_state.attempt_number,
        exception_type=type(exception).__name__ if exception else None,
        exception_message=str(exception) if exception else None,
        wait_seconds=round(wait_time, 2) if wait_time is not None else None,
        elapsed_seconds=round(elapsed, 2) if elapsed is not None else None,
    )


def log_after_retry(retry_state: RetryCallState) -> None:
    """Log after retry completes (success or final failure).

    Called by tenacity after a retry attempt completes.
    Only logs if multiple attempts were needed.

    Args:
        retry_state: Tenacity's retry state with attempt info.
    """
    # Only log if we actually retried (more than 1 attempt) and succeeded
    if retry_state.attempt_number > 1 and retry_state.outcome and not retry_state.outcome.failed:
        elapsed = retry_state.seconds_since_start
        log.info(
            "Retry succeeded",
            total_attempts=retry_state.attempt_number,
            elapsed_seconds=round(elapsed, 2) if elapsed is not None else None,
        )


# =============================================================================
# Exception Predicates
# =============================================================================


def is_retryable_gitlab_error(exception: BaseException) -> bool:
    """Check if GitLab error is retryable.

    Retryable errors:
    - GitLabServerError (5xx) - server-side issues, usually transient
    - GitLabRateLimitError (429) - rate limit hit, wait and retry

    Non-retryable errors:
    - GitLabNotFoundError (404) - resource doesn't exist
    - GitLabConflictError (409) - merge conflicts, state conflicts
    - GitLabCircuitOpenError - circuit breaker is open (fail fast)
    - Other GitLabAPIError (4xx) - client errors

    Args:
        exception: The exception to check.

    Returns:
        True if the error should be retried, False otherwise.
    """
    # Import here to avoid circular imports
    from gitlab_queue.clients.gitlab import (
        GitLabCircuitOpenError,
        GitLabRateLimitError,
        GitLabServerError,
    )

    # Circuit breaker errors are never retried - they fail fast by design
    if isinstance(exception, GitLabCircuitOpenError):
        return False

    # Server errors and rate limits are retryable
    # All other errors (including base GitLabAPIError) are not retryable
    return isinstance(exception, GitLabServerError | GitLabRateLimitError)


def is_retryable_sqlite_error(exception: BaseException) -> bool:
    """Check if SQLite error is retryable.

    Retryable errors:
    - OperationalError with "database is locked" - concurrent access
    - OperationalError with "busy" - database busy
    - Connection errors - temporary connection issues

    Non-retryable errors:
    - IntegrityError - constraint violations (duplicate key, FK)
    - ProgrammingError - SQL syntax errors

    Args:
        exception: The exception to check.

    Returns:
        True if the error should be retried, False otherwise.
    """
    # Never retry integrity errors - they indicate data issues
    if isinstance(exception, IntegrityError):
        return False

    # Check for transient SQLite errors
    if isinstance(exception, OperationalError | sqlite3.OperationalError):
        error_msg = str(exception).lower()
        transient_patterns = [
            "database is locked",
            "database table is locked",
            "busy",
            "cannot operate on a closed database",
            "disk i/o error",
        ]
        return any(pattern in error_msg for pattern in transient_patterns)

    return False


def _is_retryable_rebase_error(exception: BaseException) -> bool:
    """Check if rebase error is retryable.

    Rebase conflicts (409) are NOT retried - they require user intervention.
    Server errors during rebase API calls are retried.

    Args:
        exception: The exception to check.

    Returns:
        True if the error should be retried, False otherwise.
    """
    # Import here to avoid circular imports
    from gitlab_queue.clients.gitlab import GitLabConflictError

    # Never retry conflicts - they need user intervention
    if isinstance(exception, GitLabConflictError):
        return False

    # Retry server errors
    return is_retryable_gitlab_error(exception)


# =============================================================================
# Retry Decorators
# =============================================================================


def _create_async_retry_decorator(
    retry_predicate: Callable[[BaseException], bool],
    max_retries: int,
    initial_wait: float,
    max_wait: float,
    jitter: float,
    operation_name: str,
) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Coroutine[Any, Any, T]]]:
    """Create an async retry decorator with the given configuration.

    This is an internal factory function that eliminates code duplication
    across different retry decorator types.

    Args:
        retry_predicate: Function to determine if an exception is retryable.
        max_retries: Maximum number of retry attempts (must be >= 1).
        initial_wait: Initial wait time in seconds (must be >= 0).
        max_wait: Maximum wait time in seconds (must be >= initial_wait).
        jitter: Random jitter added to wait time (must be >= 0).
        operation_name: Name of the operation for error messages.

    Returns:
        A decorator function that wraps async functions with retry logic.

    Raises:
        ValueError: If parameters are invalid (negative values, max < initial, etc).
    """
    # Validate parameters
    if max_retries < 1:
        msg = f"max_retries must be >= 1, got {max_retries}"
        raise ValueError(msg)
    if initial_wait < 0 or max_wait < 0 or jitter < 0:
        msg = "Wait parameters (initial_wait, max_wait, jitter) must be non-negative"
        raise ValueError(msg)
    if initial_wait > max_wait:
        msg = f"initial_wait ({initial_wait}) cannot exceed max_wait ({max_wait})"
        raise ValueError(msg)

    def decorator(
        func: Callable[P, Awaitable[T]],
    ) -> Callable[P, Coroutine[Any, Any, T]]:
        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            async for attempt in AsyncRetrying(
                retry=retry_if_exception(retry_predicate),
                stop=stop_after_attempt(max_retries),
                wait=wait_exponential_jitter(
                    initial=initial_wait,
                    max=max_wait,
                    jitter=jitter,
                ),
                before_sleep=log_before_retry,
                after=log_after_retry,
                reraise=True,
            ):
                with attempt:
                    return await func(*args, **kwargs)

            # Unreachable: AsyncRetrying always raises on exhaustion with reraise=True
            raise AssertionError(f"Unreachable code in {operation_name} - tenacity bug?")

        return wrapper

    return decorator


def retry_gitlab_api(
    max_retries: int = 5,
    initial_wait: float = 1.0,
    max_wait: float = 30.0,
    jitter: float = 5.0,
) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Coroutine[Any, Any, T]]]:
    """Decorator for retrying GitLab API operations.

    Retries on server errors (5xx) and rate limits (429).
    Does NOT retry on client errors (4xx) like 404, 409.

    Args:
        max_retries: Maximum number of retry attempts. Default 5.
        initial_wait: Initial wait time in seconds. Default 1.0.
        max_wait: Maximum wait time in seconds (backoff cap). Default 30.0.
        jitter: Random jitter added to wait time. Default 5.0.

    Returns:
        Decorator function.

    Example:
        >>> @retry_gitlab_api(max_retries=3)
        ... async def get_mr(client, iid):
        ...     return await client.get_mr(iid)
    """
    return _create_async_retry_decorator(
        retry_predicate=is_retryable_gitlab_error,
        max_retries=max_retries,
        initial_wait=initial_wait,
        max_wait=max_wait,
        jitter=jitter,
        operation_name="retry_gitlab_api",
    )


def retry_sqlite(
    max_retries: int = 3,
    initial_wait: float = 0.1,
    max_wait: float = 2.0,
) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Coroutine[Any, Any, T]]]:
    """Decorator for retrying SQLite database operations.

    Retries on transient errors like database locks.
    Does NOT retry on integrity errors (constraint violations).

    Uses short wait times since SQLite locks are typically brief.

    Args:
        max_retries: Maximum number of retry attempts. Default 3.
        initial_wait: Initial wait time in seconds. Default 0.1.
        max_wait: Maximum wait time in seconds. Default 2.0.

    Returns:
        Decorator function.

    Example:
        >>> @retry_sqlite(max_retries=3)
        ... async def save_item(session, item):
        ...     session.add(item)
        ...     await session.commit()
    """
    return _create_async_retry_decorator(
        retry_predicate=is_retryable_sqlite_error,
        max_retries=max_retries,
        initial_wait=initial_wait,
        max_wait=max_wait,
        jitter=0.05,  # Minimal jitter for DB ops
        operation_name="retry_sqlite",
    )


def retry_rebase(
    max_retries: int = 3,
    initial_wait: float = 5.0,
    max_wait: float = 60.0,
) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Coroutine[Any, Any, T]]]:
    """Decorator for retrying rebase operations.

    Retries on server errors during rebase API calls.
    Does NOT retry on conflicts (GitLabConflictError) - they require
    user intervention to resolve.

    Uses longer wait times since rebase is a heavy operation.

    Args:
        max_retries: Maximum number of retry attempts. Default 3.
        initial_wait: Initial wait time in seconds. Default 5.0.
        max_wait: Maximum wait time in seconds. Default 60.0.

    Returns:
        Decorator function.

    Example:
        >>> @retry_rebase(max_retries=3)
        ... async def perform_rebase(client, mr_iid):
        ...     await client.rebase_mr(mr_iid)
        ...     return True
    """
    return _create_async_retry_decorator(
        retry_predicate=_is_retryable_rebase_error,
        max_retries=max_retries,
        initial_wait=initial_wait,
        max_wait=max_wait,
        jitter=2.0,
        operation_name="retry_rebase",
    )


__all__: list[str] = [
    "is_retryable_gitlab_error",
    "is_retryable_sqlite_error",
    "log_after_retry",
    "log_before_retry",
    "retry_gitlab_api",
    "retry_rebase",
    "retry_sqlite",
]
