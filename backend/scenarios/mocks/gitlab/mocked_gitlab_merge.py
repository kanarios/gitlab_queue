"""Mock for GitLab PUT /merge_requests/:iid/merge endpoint.

Provides mock for merging merge requests.
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
async def mocked_gitlab_merge(
    project_id: int,
    mr_iid: int,
    *,
    success: bool = True,
    merged_data: dict[str, Any] | None = None,
) -> AsyncIterator[Mocked]:
    """Mock GitLab PUT /merge_requests/:iid/merge endpoint.

    Args:
        project_id: GitLab project ID.
        mr_iid: Merge request IID.
        success: Whether merge should succeed (default: True).
        merged_data: Optional merged MR data to return.

    Yields:
        Mocked: The active mock for verification.

    Example:
        >>> async with mocked_gitlab_merge(123, 42, success=True):
        ...     await client.merge_mr(42)
    """
    matcher = jj.match("PUT", f"/api/v4/projects/{project_id}/merge_requests/{mr_iid}/merge")

    if success:
        data = merged_data or {"iid": mr_iid, "state": "merged"}
        response = jj.Response(status=200, json=data)
    else:
        response = jj.Response(status=405, json={"message": "Method Not Allowed"})

    async with mocked(matcher, response) as mock:
        yield mock


__all__ = ["mocked_gitlab_merge"]
