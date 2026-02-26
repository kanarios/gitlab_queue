"""Helper functions for repository integration tests."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from gitlab_queue.db.models import (
    AnalyticsHourlyModel,
    Base,
    MergeRequestHistoryModel,
    MergeRequestModel,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from gitlab_queue.db.database import Database


def create_test_mr_model(
    *,
    iid: int = 42,
    title: str = "Test MR",
    author_name: str = "Test User",
    author_username: str = "testuser",
    author_avatar: str | None = None,
    status: str = "queued",
    is_hotfix: int = 0,
    labels: str | None = '["merge_queue"]',
    target_branch: str = "main",
    queued_at: str | None = None,
    started_at: str | None = None,
    finished_at: str | None = None,
    pipeline_id: int | None = None,
    pipeline_status: str | None = None,
    retry_count: int = 0,
    last_error: str | None = None,
    stale_warning_sent: int = 0,
) -> MergeRequestModel:
    """
    Builds a MergeRequestModel populated with sensible defaults for testing.

    Parameters:
        iid (int): Merge request internal ID.
        title (str): Merge request title.
        author_name (str): Display name of the author.
        author_username (str): Author's username.
        author_avatar (str | None): URL or identifier for the author's avatar, if any.
        status (str): Merge request status (e.g., "queued", "merged").
        is_hotfix (int): Hotfix flag (0 or 1).
        labels (str | None): JSON-formatted string of labels (e.g., '["merge_queue"]').
        target_branch (str): Target branch name.
        queued_at (str | None): ISO 8601 timestamp for when the MR was queued. If omitted, the current UTC time is used.
        started_at (str | None): ISO 8601 timestamp for when processing started.
        finished_at (str | None): ISO 8601 timestamp for when processing finished.
        pipeline_id (int | None): Associated pipeline ID, if any.
        pipeline_status (str | None): Pipeline status string, if any.
        retry_count (int): Number of retry attempts.
        last_error (str | None): Last error message, if any.
        stale_warning_sent (int): Flag indicating whether a stale warning was sent (0 or 1).

    Returns:
        MergeRequestModel: A MergeRequestModel instance populated with the provided values and defaults.
    """
    if queued_at is None:
        queued_at = datetime.now(UTC).isoformat()
    return MergeRequestModel(
        iid=iid,
        title=title,
        author_name=author_name,
        author_username=author_username,
        author_avatar=author_avatar,
        status=status,
        is_hotfix=is_hotfix,
        labels=labels,
        target_branch=target_branch,
        queued_at=queued_at,
        started_at=started_at,
        finished_at=finished_at,
        pipeline_id=pipeline_id,
        pipeline_status=pipeline_status,
        retry_count=retry_count,
        last_error=last_error,
        stale_warning_sent=stale_warning_sent,
    )


def create_test_history_model(
    *,
    iid: int = 42,
    title: str = "Test MR",
    author_name: str = "Test User",
    author_username: str = "testuser",
    author_avatar: str | None = None,
    status: str = "merged",
    is_hotfix: int = 0,
    labels: str | None = '["merge_queue"]',
    target_branch: str = "main",
    queued_at: str | None = None,
    started_at: str | None = None,
    finished_at: str | None = None,
    wait_time_seconds: int | None = None,
    processing_time_seconds: int | None = None,
    failure_reason: str | None = None,
    pipeline_id: int | None = None,
    pipeline_status: str | None = None,
    pipeline_duration_seconds: int | None = None,
    pipeline_failed_jobs: str | None = None,
) -> MergeRequestHistoryModel:
    """
    Create a MergeRequestHistoryModel populated with sensible defaults for use in tests.

    Parameters:
        iid (int): Merge request internal ID.
        title (str): Merge request title.
        author_name (str): Display name of the author.
        author_username (str): Username of the author.
        author_avatar (str | None): URL of the author's avatar, or None.
        status (str): Final status of the merge request (e.g., "merged").
        is_hotfix (int): Integer flag indicating hotfix status (0 or 1).
        labels (str | None): JSON-encoded list of labels (e.g., '["merge_queue"]').
        target_branch (str): Target branch name.
        queued_at (str | None): ISO-formatted UTC timestamp when queued; if None, set to current UTC time.
        started_at (str | None): ISO-formatted UTC timestamp when processing started, or None.
        finished_at (str | None): ISO-formatted UTC timestamp when finished; if None, set to current UTC time.
        wait_time_seconds (int | None): Time in seconds spent waiting in queue, or None.
        processing_time_seconds (int | None): Time in seconds spent processing, or None.
        failure_reason (str | None): Reason for failure, if any.
        pipeline_id (int | None): Associated pipeline ID, or None.
        pipeline_status (str | None): Status of the pipeline, or None.
        pipeline_duration_seconds (int | None): Pipeline duration in seconds, or None.
        pipeline_failed_jobs (str | None): JSON or string describing failed pipeline jobs, or None.

    Returns:
        MergeRequestHistoryModel: A model instance with the supplied values and UTC-based defaults for missing timestamps.
    """
    if queued_at is None:
        queued_at = datetime.now(UTC).isoformat()
    if finished_at is None:
        finished_at = datetime.now(UTC).isoformat()
    return MergeRequestHistoryModel(
        iid=iid,
        title=title,
        author_name=author_name,
        author_username=author_username,
        author_avatar=author_avatar,
        status=status,
        is_hotfix=is_hotfix,
        labels=labels,
        target_branch=target_branch,
        queued_at=queued_at,
        started_at=started_at,
        finished_at=finished_at,
        wait_time_seconds=wait_time_seconds,
        processing_time_seconds=processing_time_seconds,
        failure_reason=failure_reason,
        pipeline_id=pipeline_id,
        pipeline_status=pipeline_status,
        pipeline_duration_seconds=pipeline_duration_seconds,
        pipeline_failed_jobs=pipeline_failed_jobs,
    )


def create_test_hourly_model(
    *,
    timestamp: str | None = None,
    queue_depth: int = 5,
    processed_count: int = 3,
    success_count: int = 2,
    failed_count: int = 1,
    avg_wait_time_seconds: int | None = 60,
) -> AnalyticsHourlyModel:
    """
    Constructs an AnalyticsHourlyModel representing metrics for a specific hour.

    If `timestamp` is not provided, it defaults to the current UTC hour (minutes, seconds, and microseconds zeroed) formatted as an ISO 8601 string.

    Parameters:
        timestamp (str | None): ISO 8601 timestamp for the hour; defaults to the current UTC hour when omitted.
        queue_depth (int): Number of items in the queue at the timestamp.
        processed_count (int): Number of items processed during the hour.
        success_count (int): Number of successfully processed items during the hour.
        failed_count (int): Number of failed items during the hour.
        avg_wait_time_seconds (int | None): Average wait time in seconds for processed items; may be None.

    Returns:
        AnalyticsHourlyModel: An instance populated with the supplied or default hourly metrics.
    """
    if timestamp is None:
        now = datetime.now(UTC)
        timestamp = now.replace(minute=0, second=0, microsecond=0).isoformat()
    return AnalyticsHourlyModel(
        timestamp=timestamp,
        queue_depth=queue_depth,
        processed_count=processed_count,
        success_count=success_count,
        failed_count=failed_count,
        avg_wait_time_seconds=avg_wait_time_seconds,
    )


async def seed_mr(session: AsyncSession, **kwargs) -> MergeRequestModel:
    """
    Create and persist a test MergeRequestModel in the provided session.

    Returns:
        MergeRequestModel: The created MergeRequestModel instance added to and flushed on the session.
    """
    mr = create_test_mr_model(**kwargs)
    session.add(mr)
    await session.flush()
    return mr


async def seed_history(session: AsyncSession, **kwargs) -> MergeRequestHistoryModel:
    """
    Add a test MergeRequestHistoryModel to the provided session using sensible defaults with optional overrides.

    The keyword arguments are forwarded to create_test_history_model to override default field values. The created history model is added to the session and the session is flushed before the model is returned.

    Parameters:
        session (AsyncSession): Database session to which the history model will be added.
        **kwargs: Fields to override on the generated MergeRequestHistoryModel (forwarded to create_test_history_model).

    Returns:
        MergeRequestHistoryModel: The history model instance that was added to the session and flushed.
    """
    history = create_test_history_model(**kwargs)
    session.add(history)
    await session.flush()
    return history


async def seed_hourly(session: AsyncSession, **kwargs) -> AnalyticsHourlyModel:
    """
    Create, add, and flush an AnalyticsHourlyModel in the given database session.

    Returns:
        AnalyticsHourlyModel: The created AnalyticsHourlyModel instance persisted to the session.
    """
    hourly = create_test_hourly_model(**kwargs)
    session.add(hourly)
    await session.flush()
    return hourly


async def create_tables(db: Database) -> None:
    """Create all ORM tables in the database."""
    async with db.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
