"""Helper functions for pipeline test scenarios."""

from __future__ import annotations


def create_pipeline_response(
    pipeline_id: int,
    status: str = "success",
    sha: str = "abc123",
    ref: str = "feature-branch",
) -> dict:
    """Create a GitLab pipeline API response for testing."""
    return {
        "id": pipeline_id,
        "status": status,
        "sha": sha,
        "ref": ref,
        "web_url": f"https://gitlab.com/project/-/pipelines/{pipeline_id}",
        "created_at": "2024-01-15T10:30:00Z",
    }


def create_job_response(
    job_id: int,
    name: str = "test",
    status: str = "success",
    stage: str = "test",
) -> dict:
    """Create a GitLab job API response for testing."""
    return {
        "id": job_id,
        "name": name,
        "status": status,
        "stage": stage,
        "web_url": f"https://gitlab.com/project/-/jobs/{job_id}",
    }
