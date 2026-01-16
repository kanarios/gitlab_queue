"""Pipeline and Job response factories for GitLab API mocking."""

from __future__ import annotations

from typing import Any


def pipeline_response(
    pipeline_id: int,
    *,
    status: str = "success",
    sha: str = "abc123def456",
    ref: str = "main",
    web_url: str | None = None,
    created_at: str = "2024-01-01T00:00:00.000Z",
    updated_at: str = "2024-01-01T00:00:00.000Z",
    started_at: str | None = "2024-01-01T00:00:01.000Z",
    finished_at: str | None = "2024-01-01T00:10:00.000Z",
    duration: int | None = 600,
) -> dict[str, Any]:
    """Create a valid Pipeline response dictionary.

    Args:
        pipeline_id: Pipeline ID.
        status: Pipeline status (pending, running, success, failed, canceled).
        sha: Commit SHA.
        ref: Git ref (branch or tag).
        web_url: Pipeline web URL (auto-generated if not provided).
        created_at: ISO timestamp of creation.
        updated_at: ISO timestamp of last update.
        started_at: ISO timestamp when started (None if not started).
        finished_at: ISO timestamp when finished (None if not finished).
        duration: Duration in seconds (None if not finished).

    Returns:
        Dictionary matching GitLab Pipeline API response.
    """
    if web_url is None:
        web_url = f"https://gitlab.example.com/project/-/pipelines/{pipeline_id}"

    return {
        "id": pipeline_id,
        "status": status,
        "sha": sha,
        "ref": ref,
        "web_url": web_url,
        "created_at": created_at,
        "updated_at": updated_at,
        "started_at": started_at,
        "finished_at": finished_at,
        "duration": duration,
        "coverage": None,
        "source": "push",
    }


def job_response(
    job_id: int,
    name: str,
    *,
    status: str = "success",
    stage: str = "test",
    pipeline_id: int = 1000,
    web_url: str | None = None,
    created_at: str = "2024-01-01T00:00:00.000Z",
    started_at: str | None = "2024-01-01T00:00:01.000Z",
    finished_at: str | None = "2024-01-01T00:05:00.000Z",
    duration: float | None = 300.0,
    allow_failure: bool = False,
    failure_reason: str | None = None,
) -> dict[str, Any]:
    """Create a valid Job response dictionary.

    Args:
        job_id: Job ID.
        name: Job name.
        status: Job status (pending, running, success, failed, canceled).
        stage: Job stage name.
        pipeline_id: Parent pipeline ID.
        web_url: Job web URL (auto-generated if not provided).
        created_at: ISO timestamp of creation.
        started_at: ISO timestamp when started.
        finished_at: ISO timestamp when finished.
        duration: Duration in seconds.
        allow_failure: Whether job is allowed to fail.
        failure_reason: Reason for failure (if failed).

    Returns:
        Dictionary matching GitLab Job API response.
    """
    if web_url is None:
        web_url = f"https://gitlab.example.com/project/-/jobs/{job_id}"

    return {
        "id": job_id,
        "name": name,
        "status": status,
        "stage": stage,
        "web_url": web_url,
        "created_at": created_at,
        "started_at": started_at,
        "finished_at": finished_at,
        "duration": duration,
        "allow_failure": allow_failure,
        "failure_reason": failure_reason,
        "pipeline": {
            "id": pipeline_id,
            "status": "success",
        },
        "ref": "main",
        "tag": False,
    }


__all__ = ["job_response", "pipeline_response"]
