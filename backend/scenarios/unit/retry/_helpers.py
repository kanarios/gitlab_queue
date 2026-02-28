"""Helpers for retry utility test scenarios."""

from __future__ import annotations

from sqlalchemy.exc import IntegrityError, OperationalError

from gitlab_queue.clients.gitlab import (
    GitLabAPIError,
    GitLabCircuitOpenError,
    GitLabConflictError,
    GitLabNotFoundError,
    GitLabRateLimitError,
    GitLabServerError,
)


def create_server_error() -> GitLabServerError:
    """
    Create a GitLab server error representing an HTTP 500 Internal Server Error.

    Returns:
        GitLabServerError: Instance with message "Internal Server Error" and status_code 500.
    """
    return GitLabServerError("Internal Server Error", status_code=500)


def create_rate_limit_error() -> GitLabRateLimitError:
    """
    Create a GitLab rate limit error instance for testing retry behavior.

    Returns:
        GitLabRateLimitError: An error with message "Rate limit exceeded" and `retry_after` set to 60 seconds.
    """
    return GitLabRateLimitError("Rate limit exceeded", retry_after=60)


def create_not_found_error() -> GitLabNotFoundError:
    """
    Create a GitLabNotFoundError representing an HTTP 404 Not Found.

    Returns:
        GitLabNotFoundError: Error instance with message "Not found" and status_code=404.
    """
    return GitLabNotFoundError("Not found", status_code=404)


def create_conflict_error() -> GitLabConflictError:
    """
    Create a GitLab conflict error representing an HTTP 409 response.

    Returns:
        GitLabConflictError: Error with message "Conflict" and status_code 409.
    """
    return GitLabConflictError("Conflict", status_code=409)


def create_circuit_open_error() -> GitLabCircuitOpenError:
    """
    Create a GitLabCircuitOpenError indicating the GitLab circuit breaker is open and suggesting a retry delay.

    Returns:
        GitLabCircuitOpenError: Error with retry_after set to 30.0 seconds.
    """
    return GitLabCircuitOpenError(retry_after=30.0)


def create_api_error() -> GitLabAPIError:
    """
    Create a GitLab API error representing a 400 Bad Request.

    Returns:
        GitLabAPIError: An instance with message "Bad request" and status_code 400.
    """
    return GitLabAPIError("Bad request", status_code=400)


def create_db_locked_error() -> OperationalError:
    """
    Create an OperationalError representing a locked database condition.

    The returned error uses the statement "SELECT 1", an empty parameter mapping, and an underlying exception with message "database is locked".

    Returns:
        OperationalError: An OperationalError instance indicating the database is locked.
    """
    return OperationalError("SELECT 1", {}, Exception("database is locked"))


def create_db_busy_error() -> OperationalError:
    """
    Create an OperationalError representing a busy/locked database table condition.

    Returns:
        OperationalError: An OperationalError whose statement is "SELECT 1", params is an empty dict, and whose underlying exception message is "database table is locked: busy".
    """
    return OperationalError("SELECT 1", {}, Exception("database table is locked: busy"))


def create_integrity_error() -> IntegrityError:
    """
    Create an IntegrityError representing a UNIQUE constraint violation for testing.

    Returns:
        IntegrityError: An IntegrityError for an "INSERT" statement with an underlying
        exception message "UNIQUE constraint failed".
    """
    return IntegrityError("INSERT", {}, Exception("UNIQUE constraint failed"))


def create_other_operational_error() -> OperationalError:
    """
    Create an OperationalError representing a non-retryable database error.

    Returns:
        operational_error (OperationalError): An OperationalError whose underlying exception message is "no such table: foo", simulating a non-retryable condition.
    """
    return OperationalError("SELECT 1", {}, Exception("no such table: foo"))


__all__ = [
    "create_api_error",
    "create_circuit_open_error",
    "create_conflict_error",
    "create_db_busy_error",
    "create_db_locked_error",
    "create_integrity_error",
    "create_not_found_error",
    "create_other_operational_error",
    "create_rate_limit_error",
    "create_server_error",
]
