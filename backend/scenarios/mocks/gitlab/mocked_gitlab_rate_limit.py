"""Mock for GitLab rate limit handling.

Provides mock for testing rate limit response handling.
"""

from __future__ import annotations

import time
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

import jj
from jj.mock import mocked

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from jj.mock import Mocked


@asynccontextmanager
async def mocked_gitlab_rate_limit(
    *,
    remaining: int = 100,
    limit: int = 2000,
    reset_at: int | None = None,
) -> AsyncIterator[Mocked]:
    """Mock GitLab API with rate limit headers.

    Useful for testing rate limit handling. Returns 429 when remaining is 0.

    Args:
        remaining: Remaining API calls (default: 100).
        limit: Total API limit (default: 2000).
        reset_at: Unix timestamp when limit resets.

    Yields:
        Mocked: The active mock for verification.

    Example:
        >>> async with mocked_gitlab_rate_limit(remaining=0):
        ...     # Should trigger rate limit handling
        ...     await client.get_mr(42)
    """
    reset = reset_at or int(time.time()) + 60

    matcher = jj.match("GET", "/api/v4/.*")
    headers = {
        "RateLimit-Remaining": str(remaining),
        "RateLimit-Limit": str(limit),
        "RateLimit-Reset": str(reset),
    }

    if remaining == 0:
        response = jj.Response(
            status=429,
            json={"message": "429 Too Many Requests"},
            headers={**headers, "Retry-After": "60"},
        )
    else:
        response = jj.Response(status=200, json={}, headers=headers)

    async with mocked(matcher, response) as mock:
        yield mock


__all__ = ["mocked_gitlab_rate_limit"]
