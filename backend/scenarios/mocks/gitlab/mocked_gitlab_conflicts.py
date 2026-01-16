"""Mock for GitLab GET /merge_requests/:iid/conflicts endpoint.

Provides mock for fetching merge request conflict information.
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
async def mocked_gitlab_get_conflicts(
    project_id: int,
    mr_iid: int,
    conflicts_data: list[dict[str, Any]],
    *,
    status: int = 200,
) -> AsyncIterator[Mocked]:
    """Mock GitLab GET /merge_requests/:iid/conflicts endpoint.

    Args:
        project_id: GitLab project ID.
        mr_iid: Merge request IID.
        conflicts_data: List of conflict data to return.
        status: HTTP status code (default: 200).

    Yields:
        Mocked: The active mock for verification.

    Example:
        >>> conflicts = [{"old_path": "file.py", "new_path": "file.py"}]
        >>> async with mocked_gitlab_get_conflicts(123, 42, conflicts):
        ...     files = await client.get_mr_conflicts(42)
    """
    matcher = jj.match("GET", f"/api/v4/projects/{project_id}/merge_requests/{mr_iid}/conflicts")
    response = jj.Response(status=status, json=conflicts_data)
    async with mocked(matcher, response) as mock:
        yield mock


__all__ = ["mocked_gitlab_get_conflicts"]
