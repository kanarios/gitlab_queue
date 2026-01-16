"""Mocks for GitLab comment (note) modification endpoints.

Provides mocks for:
- POST /merge_requests/:iid/notes - Add comment
- PUT /merge_requests/:iid/notes/:note_id - Update comment
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
async def mocked_gitlab_add_comment(
    project_id: int,
    mr_iid: int,
    *,
    note_id: int = 1,
    status: int = 201,
) -> AsyncIterator[Mocked]:
    """Mock GitLab POST /merge_requests/:iid/notes endpoint.

    Args:
        project_id: GitLab project ID.
        mr_iid: Merge request IID.
        note_id: ID to assign to created note (default: 1).
        status: HTTP status code (default: 201).

    Yields:
        Mocked: The active mock for verification.

    Example:
        >>> async with mocked_gitlab_add_comment(123, 42):
        ...     note_id = await client.add_comment(42, "Test comment")
    """
    matcher = jj.match("POST", f"/api/v4/projects/{project_id}/merge_requests/{mr_iid}/notes")
    response = jj.Response(status=status, json={"id": note_id, "body": ""})
    async with mocked(matcher, response) as mock:
        yield mock


@asynccontextmanager
async def mocked_gitlab_update_comment(
    project_id: int,
    mr_iid: int,
    note_id: int,
    *,
    status: int = 200,
) -> AsyncIterator[Mocked]:
    """Mock GitLab PUT /merge_requests/:iid/notes/:note_id endpoint.

    Args:
        project_id: GitLab project ID.
        mr_iid: Merge request IID.
        note_id: Note ID to update.
        status: HTTP status code (default: 200).

    Yields:
        Mocked: The active mock for verification.

    Example:
        >>> async with mocked_gitlab_update_comment(123, 42, 1):
        ...     await client.update_comment(42, 1, "Updated comment")
    """
    matcher = jj.match("PUT", f"/api/v4/projects/{project_id}/merge_requests/{mr_iid}/notes/{note_id}")
    response = jj.Response(status=status, json={"id": note_id, "body": ""})
    async with mocked(matcher, response) as mock:
        yield mock


__all__ = ["mocked_gitlab_add_comment", "mocked_gitlab_update_comment"]
