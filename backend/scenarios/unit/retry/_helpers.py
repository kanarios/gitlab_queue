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
    """Create a GitLabServerError for testing."""
    return GitLabServerError("Internal Server Error", status_code=500)


def create_rate_limit_error() -> GitLabRateLimitError:
    """Create a GitLabRateLimitError for testing."""
    return GitLabRateLimitError("Rate limit exceeded", retry_after=60)


def create_not_found_error() -> GitLabNotFoundError:
    """Create a GitLabNotFoundError for testing."""
    return GitLabNotFoundError("Not found", status_code=404)


def create_conflict_error() -> GitLabConflictError:
    """Create a GitLabConflictError for testing."""
    return GitLabConflictError("Conflict", status_code=409)


def create_circuit_open_error() -> GitLabCircuitOpenError:
    """Create a GitLabCircuitOpenError for testing."""
    return GitLabCircuitOpenError(retry_after=30.0)


def create_api_error() -> GitLabAPIError:
    """Create a plain GitLabAPIError for testing."""
    return GitLabAPIError("Bad request", status_code=400)


def create_db_locked_error() -> OperationalError:
    """Create an OperationalError with 'database is locked' message."""
    return OperationalError("SELECT 1", {}, Exception("database is locked"))


def create_db_busy_error() -> OperationalError:
    """Create an OperationalError with 'busy' in the message."""
    return OperationalError("SELECT 1", {}, Exception("database table is locked: busy"))


def create_integrity_error() -> IntegrityError:
    """Create an IntegrityError for testing."""
    return IntegrityError("INSERT", {}, Exception("UNIQUE constraint failed"))


def create_other_operational_error() -> OperationalError:
    """Create an OperationalError with a non-retryable message."""
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
