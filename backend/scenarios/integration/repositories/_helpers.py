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
    """Create a MergeRequestModel instance with sensible defaults."""
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
    """Create a MergeRequestHistoryModel instance with sensible defaults."""
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
    """Create an AnalyticsHourlyModel instance with sensible defaults."""
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
    """Create, add, and flush a MergeRequestModel in the given session."""
    mr = create_test_mr_model(**kwargs)
    session.add(mr)
    await session.flush()
    return mr


async def seed_history(session: AsyncSession, **kwargs) -> MergeRequestHistoryModel:
    """Create, add, and flush a MergeRequestHistoryModel in the given session."""
    history = create_test_history_model(**kwargs)
    session.add(history)
    await session.flush()
    return history


async def seed_hourly(session: AsyncSession, **kwargs) -> AnalyticsHourlyModel:
    """Create, add, and flush an AnalyticsHourlyModel in the given session."""
    hourly = create_test_hourly_model(**kwargs)
    session.add(hourly)
    await session.flush()
    return hourly


async def create_tables(db) -> None:
    """Create all ORM tables in the database."""
    async with db.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
