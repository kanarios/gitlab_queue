"""Mock for GitLab PUT /merge_requests/:iid/rebase endpoint.

Provides mock for initiating MR rebase operations.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

import jj
from jj.mock import mocked

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from jj.mock import Mocked


@asynccontextmanager
async def mocked_gitlab_rebase(
    project_id: int,
    mr_iid: int,
    *,
    success: bool = True,
    rebase_in_progress: bool = True,
) -> AsyncIterator[Mocked]:
    """Mock GitLab PUT /merge_requests/:iid/rebase endpoint.

    Args:
        project_id: GitLab project ID.
        mr_iid: Merge request IID.
        success: Whether rebase should succeed (default: True).
        rebase_in_progress: Whether rebase is async (default: True).

    Yields:
        Mocked: The active mock for verification.

    Example:
        >>> async with mocked_gitlab_rebase(123, 42, success=True):
        ...     await client.rebase_mr(42)
    """
    matcher = jj.match("PUT", f"/api/v4/projects/{project_id}/merge_requests/{mr_iid}/rebase")

    if success:
        response = jj.Response(status=202, json={"rebase_in_progress": rebase_in_progress})
    else:
        response = jj.Response(status=409, json={"message": "Merge conflict"})

    async with mocked(matcher, response) as mock:
        yield mock


__all__ = ["mocked_gitlab_rebase"]
