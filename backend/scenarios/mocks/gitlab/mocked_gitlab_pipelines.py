"""Mocks for GitLab pipeline endpoints.

Provides mocks for:
- GET /pipelines/:id - Get single pipeline
- GET /merge_requests/:iid/pipelines - List MR pipelines
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
async def mocked_gitlab_pipeline(
    project_id: int,
    pipeline_id: int,
    pipeline_data: dict[str, Any],
    *,
    status: int = 200,
) -> AsyncIterator[Mocked]:
    """Mock GitLab GET /pipelines/:id endpoint.

    Args:
        project_id: GitLab project ID.
        pipeline_id: Pipeline ID.
        pipeline_data: Pipeline data to return.
        status: HTTP status code (default: 200).

    Yields:
        Mocked: The active mock for verification.

    Example:
        >>> async with mocked_gitlab_pipeline(123, 456, {"id": 456, "status": "success"}):
        ...     pipeline = await client.get_pipeline(456)
    """
    matcher = jj.match("GET", f"/api/v4/projects/{project_id}/pipelines/{pipeline_id}")
    response = jj.Response(status=status, json=pipeline_data)
    async with mocked(matcher, response) as mock:
        yield mock


@asynccontextmanager
async def mocked_gitlab_mr_pipelines(
    project_id: int,
    mr_iid: int,
    pipelines_data: list[dict[str, Any]],
    *,
    status: int = 200,
) -> AsyncIterator[Mocked]:
    """Mock GitLab GET /merge_requests/:iid/pipelines endpoint.

    Args:
        project_id: GitLab project ID.
        mr_iid: Merge request IID.
        pipelines_data: List of pipeline data to return.
        status: HTTP status code (default: 200).

    Yields:
        Mocked: The active mock for verification.

    Example:
        >>> async with mocked_gitlab_mr_pipelines(123, 42, [{"id": 456, "status": "success"}]):
        ...     pipelines = await client.get_mr_pipelines(42)
    """
    matcher = jj.match("GET", f"/api/v4/projects/{project_id}/merge_requests/{mr_iid}/pipelines")
    response = jj.Response(status=status, json=pipelines_data)
    async with mocked(matcher, response) as mock:
        yield mock


__all__ = ["mocked_gitlab_mr_pipelines", "mocked_gitlab_pipeline"]
