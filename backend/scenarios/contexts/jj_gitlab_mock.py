"""JJ Remote Mock contexts for GitLab API testing.

Provides async context managers for mocking GitLab API endpoints
using the JJ remote mock library. The mock server must be running
before tests execute.

Environment:
    JJ_MOCK_URL: Base URL for JJ mock server (default: http://localhost:8080)

Example:
    >>> from scenarios.contexts.jj_gitlab_mock import mock_gitlab_get_mr
    >>>
    >>> @scenario()
    >>> async def test_get_mr():
    ...     with given:
    ...         mr_data = {"iid": 42, "title": "Test MR", "state": "opened"}
    ...     async with mock_gitlab_get_mr(42, mr_data):
    ...         with when:
    ...             result = await client.get_mr(42)
    ...         with then:
    ...             assert result.iid == 42
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

import jj
from jj.mock import mocked

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from jj.mock import Mock

# Default JJ mock server URL - can be overridden via environment variable
JJ_MOCK_URL = os.environ.get("JJ_MOCK_URL", "http://localhost:8080")


def get_mock_url() -> str:
    """Get the JJ mock server URL.

    Returns:
        str: The mock server URL from environment or default.
    """
    return JJ_MOCK_URL


@asynccontextmanager
async def mock_gitlab_get_mr(
    project_id: int,
    mr_iid: int,
    mr_data: dict[str, Any],
    *,
    status: int = 200,
) -> AsyncIterator[Mock]:
    """Mock GitLab GET /merge_requests/:iid endpoint.

    Args:
        project_id: GitLab project ID.
        mr_iid: Merge request IID.
        mr_data: MR data to return in response.
        status: HTTP status code (default: 200).

    Yields:
        Mock: The active mock for verification.

    Example:
        >>> async with mock_gitlab_get_mr(123, 42, {"iid": 42, "title": "Test"}):
        ...     result = await client.get_mr(42)
    """
    matcher = jj.match("GET", f"/api/v4/projects/{project_id}/merge_requests/{mr_iid}")
    response = jj.Response(status=status, json=mr_data)
    async with mocked(matcher, response) as mock:
        yield mock


@asynccontextmanager
async def mock_gitlab_list_mrs(
    project_id: int,
    mrs_data: list[dict[str, Any]],
    *,
    label: str | None = None,
    status: int = 200,
) -> AsyncIterator[Mock]:
    """Mock GitLab GET /merge_requests with optional label filter.

    Args:
        project_id: GitLab project ID.
        mrs_data: List of MR data to return.
        label: Optional label to filter by.
        status: HTTP status code (default: 200).

    Yields:
        Mock: The active mock for verification.

    Example:
        >>> async with mock_gitlab_list_mrs(123, [{"iid": 1}, {"iid": 2}], label="merge_queue"):
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


@asynccontextmanager
async def mock_gitlab_rebase(
    project_id: int,
    mr_iid: int,
    *,
    success: bool = True,
    rebase_in_progress: bool = True,
) -> AsyncIterator[Mock]:
    """Mock GitLab PUT /merge_requests/:iid/rebase endpoint.

    Args:
        project_id: GitLab project ID.
        mr_iid: Merge request IID.
        success: Whether rebase should succeed (default: True).
        rebase_in_progress: Whether rebase is async (default: True).

    Yields:
        Mock: The active mock for verification.

    Example:
        >>> async with mock_gitlab_rebase(123, 42, success=True):
        ...     await client.rebase_mr(42)
    """
    matcher = jj.match("PUT", f"/api/v4/projects/{project_id}/merge_requests/{mr_iid}/rebase")

    if success:
        response = jj.Response(status=202, json={"rebase_in_progress": rebase_in_progress})
    else:
        response = jj.Response(status=409, json={"message": "Merge conflict"})

    async with mocked(matcher, response) as mock:
        yield mock


@asynccontextmanager
async def mock_gitlab_merge(
    project_id: int,
    mr_iid: int,
    *,
    success: bool = True,
    merged_data: dict[str, Any] | None = None,
) -> AsyncIterator[Mock]:
    """Mock GitLab PUT /merge_requests/:iid/merge endpoint.

    Args:
        project_id: GitLab project ID.
        mr_iid: Merge request IID.
        success: Whether merge should succeed (default: True).
        merged_data: Optional merged MR data to return.

    Yields:
        Mock: The active mock for verification.

    Example:
        >>> async with mock_gitlab_merge(123, 42, success=True):
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


@asynccontextmanager
async def mock_gitlab_pipeline(
    project_id: int,
    pipeline_id: int,
    pipeline_data: dict[str, Any],
    *,
    status: int = 200,
) -> AsyncIterator[Mock]:
    """Mock GitLab GET /pipelines/:id endpoint.

    Args:
        project_id: GitLab project ID.
        pipeline_id: Pipeline ID.
        pipeline_data: Pipeline data to return.
        status: HTTP status code (default: 200).

    Yields:
        Mock: The active mock for verification.

    Example:
        >>> async with mock_gitlab_pipeline(123, 456, {"id": 456, "status": "success"}):
        ...     pipeline = await client.get_pipeline(456)
    """
    matcher = jj.match("GET", f"/api/v4/projects/{project_id}/pipelines/{pipeline_id}")
    response = jj.Response(status=status, json=pipeline_data)
    async with mocked(matcher, response) as mock:
        yield mock


@asynccontextmanager
async def mock_gitlab_mr_pipelines(
    project_id: int,
    mr_iid: int,
    pipelines_data: list[dict[str, Any]],
    *,
    status: int = 200,
) -> AsyncIterator[Mock]:
    """Mock GitLab GET /merge_requests/:iid/pipelines endpoint.

    Args:
        project_id: GitLab project ID.
        mr_iid: Merge request IID.
        pipelines_data: List of pipeline data to return.
        status: HTTP status code (default: 200).

    Yields:
        Mock: The active mock for verification.

    Example:
        >>> async with mock_gitlab_mr_pipelines(123, 42, [{"id": 456, "status": "success"}]):
        ...     pipelines = await client.get_mr_pipelines(42)
    """
    matcher = jj.match("GET", f"/api/v4/projects/{project_id}/merge_requests/{mr_iid}/pipelines")
    response = jj.Response(status=status, json=pipelines_data)
    async with mocked(matcher, response) as mock:
        yield mock


@asynccontextmanager
async def mock_gitlab_add_comment(
    project_id: int,
    mr_iid: int,
    *,
    note_id: int = 1,
    status: int = 201,
) -> AsyncIterator[Mock]:
    """Mock GitLab POST /merge_requests/:iid/notes endpoint.

    Args:
        project_id: GitLab project ID.
        mr_iid: Merge request IID.
        note_id: ID to assign to created note (default: 1).
        status: HTTP status code (default: 201).

    Yields:
        Mock: The active mock for verification.

    Example:
        >>> async with mock_gitlab_add_comment(123, 42):
        ...     note_id = await client.add_comment(42, "Test comment")
    """
    matcher = jj.match("POST", f"/api/v4/projects/{project_id}/merge_requests/{mr_iid}/notes")
    response = jj.Response(status=status, json={"id": note_id, "body": ""})
    async with mocked(matcher, response) as mock:
        yield mock


@asynccontextmanager
async def mock_gitlab_update_comment(
    project_id: int,
    mr_iid: int,
    note_id: int,
    *,
    status: int = 200,
) -> AsyncIterator[Mock]:
    """Mock GitLab PUT /merge_requests/:iid/notes/:note_id endpoint.

    Args:
        project_id: GitLab project ID.
        mr_iid: Merge request IID.
        note_id: Note ID to update.
        status: HTTP status code (default: 200).

    Yields:
        Mock: The active mock for verification.

    Example:
        >>> async with mock_gitlab_update_comment(123, 42, 1):
        ...     await client.update_comment(42, 1, "Updated comment")
    """
    matcher = jj.match(
        "PUT", f"/api/v4/projects/{project_id}/merge_requests/{mr_iid}/notes/{note_id}"
    )
    response = jj.Response(status=status, json={"id": note_id, "body": ""})
    async with mocked(matcher, response) as mock:
        yield mock


@asynccontextmanager
async def mock_gitlab_rate_limit(
    *,
    remaining: int = 100,
    limit: int = 2000,
    reset_at: int | None = None,
) -> AsyncIterator[Mock]:
    """Mock GitLab API with rate limit headers.

    Useful for testing rate limit handling. Returns 429 when remaining is 0.

    Args:
        remaining: Remaining API calls (default: 100).
        limit: Total API limit (default: 2000).
        reset_at: Unix timestamp when limit resets.

    Yields:
        Mock: The active mock for verification.

    Example:
        >>> async with mock_gitlab_rate_limit(remaining=0):
        ...     # Should trigger rate limit handling
        ...     await client.get_mr(42)
    """
    import time

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


@asynccontextmanager
async def mock_gitlab_get_notes(
    project_id: int,
    mr_iid: int,
    notes_data: list[dict[str, Any]],
    *,
    status: int = 200,
) -> AsyncIterator[Mock]:
    """Mock GitLab GET /merge_requests/:iid/notes endpoint.

    Args:
        project_id: GitLab project ID.
        mr_iid: Merge request IID.
        notes_data: List of note data to return.
        status: HTTP status code (default: 200).

    Yields:
        Mock: The active mock for verification.

    Example:
        >>> async with mock_gitlab_get_notes(123, 42, [{"id": 1, "body": "comment"}]):
        ...     notes = await client.get_list("/merge_requests/42/notes")
    """
    matcher = jj.match("GET", f"/api/v4/projects/{project_id}/merge_requests/{mr_iid}/notes")
    response = jj.Response(status=status, json=notes_data)
    async with mocked(matcher, response) as mock:
        yield mock


@asynccontextmanager
async def mock_gitlab_get_conflicts(
    project_id: int,
    mr_iid: int,
    conflicts_data: list[dict[str, Any]],
    *,
    status: int = 200,
) -> AsyncIterator[Mock]:
    """Mock GitLab GET /merge_requests/:iid/conflicts endpoint.

    Args:
        project_id: GitLab project ID.
        mr_iid: Merge request IID.
        conflicts_data: List of conflict data to return.
        status: HTTP status code (default: 200).

    Yields:
        Mock: The active mock for verification.

    Example:
        >>> conflicts = [{"old_path": "file.py", "new_path": "file.py"}]
        >>> async with mock_gitlab_get_conflicts(123, 42, conflicts):
        ...     files = await client.get_mr_conflicts(42)
    """
    matcher = jj.match("GET", f"/api/v4/projects/{project_id}/merge_requests/{mr_iid}/conflicts")
    response = jj.Response(status=status, json=conflicts_data)
    async with mocked(matcher, response) as mock:
        yield mock


@asynccontextmanager
async def mock_gitlab_retry_job(
    project_id: int,
    job_id: int,
    job_data: dict[str, Any],
    *,
    status: int = 200,
) -> AsyncIterator[Mock]:
    """Mock GitLab POST /jobs/:id/retry endpoint.

    Args:
        project_id: GitLab project ID.
        job_id: Job ID to retry.
        job_data: Job data to return after retry.
        status: HTTP status code (default: 200).

    Yields:
        Mock: The active mock for verification.

    Example:
        >>> job_data = {"id": 123, "name": "test", "status": "pending"}
        >>> async with mock_gitlab_retry_job(123, 456, job_data):
        ...     job = await client.retry_pipeline_job(456)
    """
    matcher = jj.match("POST", f"/api/v4/projects/{project_id}/jobs/{job_id}/retry")
    response = jj.Response(status=status, json=job_data)
    async with mocked(matcher, response) as mock:
        yield mock


@asynccontextmanager
async def mock_gitlab_pipeline_jobs(
    project_id: int,
    pipeline_id: int,
    jobs_data: list[dict[str, Any]],
    *,
    status: int = 200,
) -> AsyncIterator[Mock]:
    """Mock GitLab GET /pipelines/:id/jobs endpoint.

    Args:
        project_id: GitLab project ID.
        pipeline_id: Pipeline ID.
        jobs_data: List of job data to return.
        status: HTTP status code (default: 200).

    Yields:
        Mock: The active mock for verification.

    Example:
        >>> jobs = [{"id": 1, "name": "test", "status": "success"}]
        >>> async with mock_gitlab_pipeline_jobs(123, 456, jobs):
        ...     jobs = await client.get_pipeline_jobs(456)
    """
    matcher = jj.match("GET", f"/api/v4/projects/{project_id}/pipelines/{pipeline_id}/jobs")
    response = jj.Response(status=status, json=jobs_data)
    async with mocked(matcher, response) as mock:
        yield mock


__all__ = [
    "JJ_MOCK_URL",
    "get_mock_url",
    "mock_gitlab_add_comment",
    "mock_gitlab_get_conflicts",
    "mock_gitlab_get_mr",
    "mock_gitlab_get_notes",
    "mock_gitlab_list_mrs",
    "mock_gitlab_merge",
    "mock_gitlab_mr_pipelines",
    "mock_gitlab_pipeline",
    "mock_gitlab_pipeline_jobs",
    "mock_gitlab_rate_limit",
    "mock_gitlab_rebase",
    "mock_gitlab_retry_job",
    "mock_gitlab_update_comment",
]
