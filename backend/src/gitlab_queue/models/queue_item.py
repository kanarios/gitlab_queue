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
        expected_sha: SHA expected for current pipeline (for race condition prevention)
        retry_count: Max number of retry attempts made across all jobs
        retried_jobs: Per-job retry counts {job_name: count} persisted to DB
        last_error: Most recent error message if any
        stale_warning_sent: Whether stale warning has been sent for this MR
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
    expected_sha: str | None = None
    retry_count: int = 0  # legacy: kept for DB compat; prefer get_max_job_retry_count()
    retried_jobs: dict[str, int] = field(default_factory=dict)
    last_error: str | None = None
    stale_warning_sent: bool = False
    processing_attempts: int = 0

    def get_max_job_retry_count(self) -> int:
        """Return the highest retry count across all retried jobs.

        When ``retried_jobs`` is populated, returns the maximum per-job
        retry count (e.g. ``{"lint": 2, "test": 1}`` → ``2``).
        Falls back to legacy ``retry_count`` for backward compatibility.
        """
        if self.retried_jobs:
            return max(self.retried_jobs.values())
        return self.retry_count


@dataclass(frozen=True, slots=True)
class DashboardStats:
    """Aggregate statistics for queue dashboard.

    Provides computed metrics over a rolling time window for
    display on the status dashboard.

    Attributes:
        total_in_queue: Current number of MRs in active queue.
        merged_count: Number of successfully merged MRs in window.
        failed_count: Number of failed MRs in window.
        success_rate: Percentage of successful merges (0-100).
        avg_wait_seconds: Average time from queued to processing start.
        avg_processing_seconds: Average time from start to merge.
        stats_window_days: Number of days included in statistics.
    """

    total_in_queue: int
    merged_count: int
    failed_count: int
    success_rate: float
    avg_wait_seconds: float
    avg_processing_seconds: float
    stats_window_days: int


__all__: list[str] = ["DashboardStats", "QueueItem"]
