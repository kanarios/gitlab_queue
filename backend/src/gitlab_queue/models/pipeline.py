"""Pipeline and Job data models for GitLab Merge Queue Bot.

Provides immutable dataclass representations of GitLab pipelines and jobs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime


@dataclass(frozen=True, slots=True)
class Pipeline:
    """GitLab Pipeline representation.

    Immutable dataclass for pipeline data from GitLab API.

    Attributes:
        id: Pipeline ID
        status: Pipeline status (pending, running, success, failed, canceled)
        sha: Commit SHA the pipeline runs on
        ref: Branch or tag name
        web_url: URL to the pipeline in GitLab UI
        created_at: When the pipeline was created
    """

    id: int
    status: str
    sha: str
    ref: str
    web_url: str | None = None
    created_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class Job:
    """GitLab Job representation.

    Immutable dataclass for job data from GitLab API.

    Attributes:
        id: Job ID
        name: Job name
        status: Job status (pending, running, success, failed, canceled, etc.)
        stage: Pipeline stage this job belongs to
        web_url: URL to the job in GitLab UI
    """

    id: int
    name: str
    status: str
    stage: str
    web_url: str | None = None


__all__: list[str] = ["Job", "Pipeline"]
