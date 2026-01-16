"""Error response factories for GitLab API mocking."""

from __future__ import annotations

from typing import Any


def not_found_response(
    message: str = "404 Not Found",
) -> dict[str, Any]:
    """Create a 404 Not Found error response.

    Args:
        message: Error message.

    Returns:
        Dictionary matching GitLab error response.
    """
    return {"message": message}


def conflict_response(
    message: str = "409 Conflict",
) -> dict[str, Any]:
    """Create a 409 Conflict error response.

    Used for merge conflicts, rebase conflicts, etc.

    Args:
        message: Error message.

    Returns:
        Dictionary matching GitLab error response.
    """
    return {"message": message}


def rate_limit_response(
    message: str = "429 Too Many Requests",
) -> dict[str, Any]:
    """Create a 429 Rate Limit error response.

    Args:
        message: Error message.

    Returns:
        Dictionary matching GitLab error response.
    """
    return {"message": message}


def server_error_response(
    message: str = "500 Internal Server Error",
) -> dict[str, Any]:
    """Create a 500 Server Error response.

    Args:
        message: Error message.

    Returns:
        Dictionary matching GitLab error response.
    """
    return {"message": message}


__all__ = [
    "conflict_response",
    "not_found_response",
    "rate_limit_response",
    "server_error_response",
]
