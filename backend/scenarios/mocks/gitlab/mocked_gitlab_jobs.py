"""Mocks for GitLab job-related endpoints.

Provides mocks for:
- POST /jobs/:id/retry - Retry a job
- GET /pipelines/:id/jobs - List pipeline jobs
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
async def mocked_gitlab_retry_job(
    project_id: int,
    job_id: int,
    job_data: dict[str, Any],
    *,
    status: int = 200,
) -> AsyncIterator[Mocked]:
    """Mock GitLab POST /jobs/:id/retry endpoint.

    Args:
        project_id: GitLab project ID.
        job_id: Job ID to retry.
        job_data: Job data to return after retry.
        status: HTTP status code (default: 200).

    Yields:
        Mocked: The active mock for verification.

    Example:
        >>> job_data = {"id": 123, "name": "test", "status": "pending"}
        >>> async with mocked_gitlab_retry_job(123, 456, job_data):
        ...     job = await client.retry_pipeline_job(456)
    """
    matcher = jj.match("POST", f"/api/v4/projects/{project_id}/jobs/{job_id}/retry")
    response = jj.Response(status=status, json=job_data)
    async with mocked(matcher, response) as mock:
        yield mock


@asynccontextmanager
async def mocked_gitlab_pipeline_jobs(
    project_id: int,
    pipeline_id: int,
    jobs_data: list[dict[str, Any]],
    *,
    status: int = 200,
) -> AsyncIterator[Mocked]:
    """Mock GitLab GET /pipelines/:id/jobs endpoint.

    Args:
        project_id: GitLab project ID.
        pipeline_id: Pipeline ID.
        jobs_data: List of job data to return.
        status: HTTP status code (default: 200).

    Yields:
        Mocked: The active mock for verification.

    Example:
        >>> jobs = [{"id": 1, "name": "test", "status": "success"}]
        >>> async with mocked_gitlab_pipeline_jobs(123, 456, jobs):
        ...     jobs = await client.get_pipeline_jobs(456)
    """
    matcher = jj.match("GET", f"/api/v4/projects/{project_id}/pipelines/{pipeline_id}/jobs")
    response = jj.Response(status=status, json=jobs_data)
    async with mocked(matcher, response) as mock:
        yield mock


__all__ = ["mocked_gitlab_pipeline_jobs", "mocked_gitlab_retry_job"]
