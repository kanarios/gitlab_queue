"""Mock for GitLab GET /merge_requests endpoint.

Provides mock for listing merge requests with optional label filtering.
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
async def mocked_gitlab_list_mrs(
    project_id: int,
    mrs_data: list[dict[str, Any]],
    *,
    label: str | None = None,
    status: int = 200,
) -> AsyncIterator[Mocked]:
    """Mock GitLab GET /merge_requests with optional label filter.

    Args:
        project_id: GitLab project ID.
        mrs_data: List of MR data to return.
        label: Optional label to filter by.
        status: HTTP status code (default: 200).

    Yields:
        Mocked: The active mock for verification.

    Example:
        >>> async with mocked_gitlab_list_mrs(123, [{"iid": 1}, {"iid": 2}], label="merge_queue"):
        ...     mrs = await client.list_mrs_with_label("merge_queue")
    """
    if label:
        matcher = jj.match(
            "GET",
            f"/api/v4/projects/{project_id}/merge_requests",
            params={"labels": label},
        )
    else:
        matcher = jj.match("GET", f"/api/v4/projects/{project_id}/merge_requests")

    response = jj.Response(status=status, json=mrs_data)
    async with mocked(matcher, response) as mock:
        yield mock


__all__ = ["mocked_gitlab_list_mrs"]
