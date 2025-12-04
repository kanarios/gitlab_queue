"""QueueItem data model for GitLab Merge Queue Bot.

Provides mutable dataclass representation of an MR in the merge queue.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime


@dataclass(slots=True)
class QueueItem:
    """Queue item representing an MR in the merge queue.

    Mutable dataclass (NOT frozen) since state changes during processing.
    Uses slots=True for memory efficiency.

    Attributes:
        mr_iid: Internal ID (project-scoped MR number)
        title: MR title for display
        author_name: Author's display name
        author_username: Author's GitLab username
        target_branch: Branch the MR targets (e.g., 'master')
        state: Current queue state (queued, rebasing, testing, merging, merged, failed, removed)
        queued_at: When the MR was added to the queue
        is_hotfix: Whether this MR has hotfix priority
        author_avatar: Author's avatar URL (optional)
        labels: List of label names on the MR
        started_at: When processing started (rebase began)
        finished_at: When processing finished (merged, failed, or removed)
        pipeline_id: Current pipeline ID if running
        pipeline_status: Current pipeline status
        retry_count: Number of retry attempts for pipeline failures
        last_error: Most recent error message if any
    """

    # Required fields (no defaults)
    mr_iid: int
    title: str
    author_name: str
    author_username: str
    target_branch: str
    state: str
    queued_at: datetime

    # Optional fields (with defaults)
    is_hotfix: bool = False
    author_avatar: str | None = None
    labels: list[str] = field(default_factory=list)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    pipeline_id: int | None = None
    pipeline_status: str | None = None
    retry_count: int = 0
    last_error: str | None = None


__all__: list[str] = ["QueueItem"]
