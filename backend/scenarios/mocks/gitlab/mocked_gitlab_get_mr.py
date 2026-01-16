"""Mock for GitLab GET /merge_requests/:iid endpoint.

Provides mock for fetching individual merge request details.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

import jj
from jj.mock import mocked

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from jj.mock import Mocked


@asynccontextmanager
async def mocked_gitlab_get_mr(
    project_id: int,
    mr_iid: int,
    mr_data: dict[str, Any],
    *,
    status: int = 200,
) -> AsyncIterator[Mocked]:
    """Mock GitLab GET /merge_requests/:iid endpoint.

    Args:
        project_id: GitLab project ID.
        mr_iid: Merge request IID.
        mr_data: MR data to return in response.
        status: HTTP status code (default: 200).

    Yields:
        Mocked: The active mock for verification.

    Example:
        >>> async with mocked_gitlab_get_mr(123, 42, {"iid": 42, "title": "Test"}):
        ...     result = await client.get_mr(42)
    """
    matcher = jj.match("GET", f"/api/v4/projects/{project_id}/merge_requests/{mr_iid}")
    response = jj.Response(status=status, json=mr_data)
    async with mocked(matcher, response) as mock:
        yield mock


__all__ = ["mocked_gitlab_get_mr"]
