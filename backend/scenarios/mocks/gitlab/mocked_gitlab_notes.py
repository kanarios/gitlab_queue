"""Mock for GitLab GET /merge_requests/:iid/notes endpoint.

Provides mock for listing merge request notes (comments).
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
async def mocked_gitlab_get_notes(
    project_id: int,
    mr_iid: int,
    notes_data: list[dict[str, Any]],
    *,
    status: int = 200,
) -> AsyncIterator[Mocked]:
    """Mock GitLab GET /merge_requests/:iid/notes endpoint.

    Args:
        project_id: GitLab project ID.
        mr_iid: Merge request IID.
        notes_data: List of note data to return.
        status: HTTP status code (default: 200).

    Yields:
        Mocked: The active mock for verification.

    Example:
        >>> async with mocked_gitlab_get_notes(123, 42, [{"id": 1, "body": "comment"}]):
        ...     notes = await client.get_list("/merge_requests/42/notes")
    """
    matcher = jj.match("GET", f"/api/v4/projects/{project_id}/merge_requests/{mr_iid}/notes")
    response = jj.Response(status=status, json=notes_data)
    async with mocked(matcher, response) as mock:
        yield mock


__all__ = ["mocked_gitlab_get_notes"]
