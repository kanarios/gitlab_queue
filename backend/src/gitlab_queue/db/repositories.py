"""Repository Pattern implementation for GitLab Merge Queue Bot.

Provides clean abstraction layer between business logic and database operations,
using SQLAlchemy ORM with async support.

Example:
    >>> from gitlab_queue.db import Database, UnitOfWork
    >>> async with Database("sqlite+aiosqlite:///data/queue.db") as db:
    ...     async with UnitOfWork(db, auto_commit=True) as uow:
    ...         mr = await uow.merge_requests.get_by_iid(42)
    ...         await uow.merge_requests.complete_mr(42, "merged")
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING, Any

from sqlalchemy import and_, case, delete, func, select

from gitlab_queue.db.models import (
    AnalyticsDailyModel,
    AnalyticsHourlyModel,
    MergeRequestHistoryModel,
    MergeRequestModel,
)
from gitlab_queue.utils.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlalchemy.ext.asyncio import AsyncSession

    from gitlab_queue.db.database import Database
    from gitlab_queue.models.queue_item import QueueItem


log = get_logger(__name__)


# =============================================================================
# Exceptions
# =============================================================================


class RepositoryError(Exception):
    """Base exception for repository operations."""


class MergeRequestNotFoundError(RepositoryError):
    """Raised when a merge request is not found."""

    def __init__(self, iid: int) -> None:
        self.iid = iid
        super().__init__(f"Merge request !{iid} not found")


class DuplicateRecordError(RepositoryError):
    """Raised when attempting to create a duplicate record."""


# =============================================================================
# Data Classes
# =============================================================================


@dataclass(frozen=True, slots=True)
class CompleteMRResult:
    """Result of completing an MR (moving to history)."""

    success: bool
    history_id: int | None = None
    error: str | None = None


@dataclass(frozen=True, slots=True)
class PaginatedResult[T]:
    """Paginated query result."""

    items: Sequence[T]
    total: int
    page: int
    per_page: int
    total_pages: int


@dataclass(frozen=True, slots=True)
class PeriodStats:
    """Statistics for a time period."""

    total_processed: int
    success_count: int
    failed_count: int
    conflict_count: int
    timeout_count: int
    hotfix_count: int
    avg_wait_time_seconds: float | None
    avg_processing_time_seconds: float | None


@dataclass(frozen=True, slots=True)
class DashboardMetrics:
    """Metrics for dashboard display."""

    total_in_queue: int
    merged_count: int
    failed_count: int
    success_rate: float
    avg_wait_seconds: float
    avg_processing_seconds: float
    hourly_trend: list[dict[str, Any]]
    daily_stats: list[dict[str, Any]]


# =============================================================================
# Active Queue States
# =============================================================================

ACTIVE_STATES: tuple[str, ...] = ("queued", "rebasing", "testing", "merging")
TERMINAL_STATES: tuple[str, ...] = ("merged", "failed", "removed")


# =============================================================================
# MergeRequestRepository
# =============================================================================


class MergeRequestRepository:
    """Repository for active merge requests in the queue.

    Handles CRUD operations and state transitions for MRs
    currently being processed.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # =========================================================================
    # Read Operations
    # =========================================================================

    async def get_by_iid(self, iid: int) -> MergeRequestModel | None:
        """Get MR by its GitLab internal ID.

        Args:
            iid: The MR's project-scoped internal ID.

        Returns:
            MergeRequestModel if found, None otherwise.
        """
        stmt = select(MergeRequestModel).where(MergeRequestModel.iid == iid)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all_active(self) -> Sequence[MergeRequestModel]:
        """Get all MRs in active queue states.

        Returns MRs ordered by hotfix priority (DESC) then queued_at (ASC).
        """
        stmt = (
            select(MergeRequestModel)
            .where(MergeRequestModel.status.in_(ACTIVE_STATES))
            .order_by(MergeRequestModel.is_hotfix.desc(), MergeRequestModel.queued_at.asc())
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def get_next_queued(self) -> MergeRequestModel | None:
        """Get next MR ready for processing.

        Returns the first MR with status 'queued', ordered by priority.
        """
        stmt = (
            select(MergeRequestModel)
            .where(MergeRequestModel.status == "queued")
            .order_by(MergeRequestModel.is_hotfix.desc(), MergeRequestModel.queued_at.asc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_status(self, status: str) -> Sequence[MergeRequestModel]:
        """Get all MRs with a specific status."""
        stmt = select(MergeRequestModel).where(MergeRequestModel.status == status)
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def count_active(self) -> int:
        """Count MRs in active queue states."""
        stmt = select(func.count()).select_from(MergeRequestModel).where(MergeRequestModel.status.in_(ACTIVE_STATES))
        result = await self._session.execute(stmt)
        return result.scalar() or 0

    async def count_by_status(self) -> dict[str, int]:
        """Get count of MRs grouped by status.

        Returns:
            Dict mapping status to count for active states.
        """
        stmt = (
            select(MergeRequestModel.status, func.count())
            .where(MergeRequestModel.status.in_(ACTIVE_STATES))
            .group_by(MergeRequestModel.status)
        )
        result = await self._session.execute(stmt)

        # Initialize all states with 0
        counts: dict[str, int] = dict.fromkeys(ACTIVE_STATES, 0)
        for status, count in result.all():
            counts[status] = count
        return counts

    async def get_stale_mrs(self, hours: int) -> Sequence[MergeRequestModel]:
        """Get MRs that have been queued longer than threshold hours.

        Only returns MRs that haven't received a stale warning yet.
        """
        threshold = datetime.now(UTC) - timedelta(hours=hours)
        threshold_str = threshold.isoformat()

        stmt = (
            select(MergeRequestModel)
            .where(
                and_(
                    MergeRequestModel.status.in_(ACTIVE_STATES),
                    MergeRequestModel.stale_warning_sent == 0,
                    MergeRequestModel.queued_at < threshold_str,
                )
            )
            .order_by(MergeRequestModel.queued_at.asc())
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def get_position(self, iid: int) -> int | None:
        """Get the position of an MR in the queue.

        Returns:
            1-indexed position, or None if MR not found or not in active state.
        """
        mr = await self.get_by_iid(iid)
        if mr is None or mr.status not in ACTIVE_STATES:
            return None

        # Count MRs ahead of this one
        stmt = (
            select(func.count())
            .select_from(MergeRequestModel)
            .where(
                and_(
                    MergeRequestModel.status.in_(ACTIVE_STATES),
                    # Hotfixes come first, then by queued_at
                    (
                        (MergeRequestModel.is_hotfix > mr.is_hotfix)
                        | ((MergeRequestModel.is_hotfix == mr.is_hotfix) & (MergeRequestModel.queued_at < mr.queued_at))
                    ),
                )
            )
        )
        result = await self._session.execute(stmt)
        ahead_count = result.scalar() or 0
        return ahead_count + 1

    # =========================================================================
    # Write Operations
    # =========================================================================

    async def add(self, mr: MergeRequestModel) -> MergeRequestModel:
        """Add new MR to the queue."""
        self._session.add(mr)
        await self._session.flush()
        return mr

    async def add_if_not_exists(
        self,
        iid: int,
        title: str,
        author_name: str,
        author_username: str,
        author_avatar: str | None,
        is_hotfix: bool,
        labels: list[str],
        target_branch: str,
    ) -> MergeRequestModel:
        """Add MR if not already in queue (idempotent).

        Returns existing MR if already present.
        """
        existing = await self.get_by_iid(iid)
        if existing:
            return existing

        mr = MergeRequestModel(
            iid=iid,
            title=title,
            author_name=author_name,
            author_username=author_username,
            author_avatar=author_avatar,
            is_hotfix=1 if is_hotfix else 0,
            labels=json.dumps(labels),
            target_branch=target_branch,
            status="queued",
            queued_at=datetime.now(UTC).isoformat(),
        )
        return await self.add(mr)

    async def update_status(self, iid: int, status: str, *, auto_timestamps: bool = True) -> bool:
        """Update MR status.

        Args:
            iid: MR internal ID.
            status: New status.
            auto_timestamps: If True, auto-set started_at and finished_at.

        Returns:
            True if updated, False if not found.
        """
        mr = await self.get_by_iid(iid)
        if not mr:
            return False

        mr.status = status

        if auto_timestamps:
            now = datetime.now(UTC).isoformat()
            # Auto-set started_at on first processing
            if mr.started_at is None and status != "queued":
                mr.started_at = now
            # Auto-set finished_at for terminal states
            if status in TERMINAL_STATES:
                mr.finished_at = now

        await self._session.flush()
        return True

    async def update(self, iid: int, **fields: Any) -> bool:
        """Update arbitrary fields on an MR.

        Args:
            iid: MR internal ID.
            **fields: Field name -> value pairs to update.

        Returns:
            True if updated, False if not found.
        """
        mr = await self.get_by_iid(iid)
        if not mr:
            return False

        allowed_fields = {
            "status",
            "pipeline_id",
            "pipeline_status",
            "last_error",
            "retry_count",
            "stale_warning_sent",
            "started_at",
            "finished_at",
        }

        for field, value in fields.items():
            if field in allowed_fields:
                setattr(mr, field, value)

        await self._session.flush()
        return True

    async def delete(self, iid: int) -> bool:
        """Hard delete MR from active queue.

        Note: Prefer using complete_mr() to preserve history.
        """
        mr = await self.get_by_iid(iid)
        if not mr:
            return False

        await self._session.delete(mr)
        await self._session.flush()
        return True

    # =========================================================================
    # Complex Operations
    # =========================================================================

    async def complete_mr(
        self,
        iid: int,
        status: str,
        failure_reason: str | None = None,
        pipeline_duration_seconds: int | None = None,
        pipeline_failed_jobs: str | None = None,
    ) -> CompleteMRResult:
        """Move MR from active queue to history.

        This is an atomic operation that:
        1. Reads the MR from active queue
        2. Creates history record with computed timing fields
        3. Deletes from active queue

        Args:
            iid: MR internal ID.
            status: Final status (merged, failed, conflict, timeout, removed).
            failure_reason: Reason for failure if applicable.
            pipeline_duration_seconds: Total pipeline duration.
            pipeline_failed_jobs: JSON array of failed job names.

        Returns:
            CompleteMRResult with success status and history ID.
        """
        mr = await self.get_by_iid(iid)
        if not mr:
            return CompleteMRResult(success=False, error=f"MR {iid} not found")

        now = datetime.now(UTC)
        finished_at = now.isoformat()

        # Parse timestamps for timing calculations
        queued_at = datetime.fromisoformat(mr.queued_at) if mr.queued_at else now
        started_at = datetime.fromisoformat(mr.started_at) if mr.started_at else None

        # Calculate timing metrics
        wait_time_seconds: int | None = None
        processing_time_seconds: int | None = None

        if started_at:
            wait_time_seconds = int((started_at - queued_at).total_seconds())
            processing_time_seconds = int((now - started_at).total_seconds())

        # Create history record
        history = MergeRequestHistoryModel(
            iid=mr.iid,
            title=mr.title,
            author_name=mr.author_name,
            author_username=mr.author_username,
            author_avatar=mr.author_avatar,
            status=status,
            is_hotfix=mr.is_hotfix,
            labels=mr.labels,
            target_branch=mr.target_branch,
            queued_at=mr.queued_at,
            started_at=mr.started_at,
            finished_at=finished_at,
            wait_time_seconds=wait_time_seconds,
            processing_time_seconds=processing_time_seconds,
            failure_reason=failure_reason,
            pipeline_id=mr.pipeline_id,
            pipeline_status=mr.pipeline_status,
            pipeline_duration_seconds=pipeline_duration_seconds,
            pipeline_failed_jobs=pipeline_failed_jobs,
        )

        self._session.add(history)
        await self._session.delete(mr)
        await self._session.flush()

        log.info(
            "MR completed and moved to history",
            iid=iid,
            status=status,
            wait_time_seconds=wait_time_seconds,
            processing_time_seconds=processing_time_seconds,
        )

        return CompleteMRResult(success=True, history_id=history.id)


# =============================================================================
# HistoryRepository
# =============================================================================


class HistoryRepository:
    """Repository for completed merge request history.

    Provides paginated search and statistics for historical data.
    Retention: 1 year.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_history(
        self,
        page: int = 1,
        per_page: int = 20,
        status_filter: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        author_username: str | None = None,
    ) -> PaginatedResult[MergeRequestHistoryModel]:
        """Get paginated history with optional filters.

        Args:
            page: Page number (1-indexed).
            per_page: Items per page (max 100).
            status_filter: Filter by status (merged, failed, etc.).
            date_from: Filter finished_at >= date.
            date_to: Filter finished_at <= date.
            author_username: Filter by author.

        Returns:
            PaginatedResult with items and pagination metadata.
        """
        per_page = min(per_page, 100)  # Cap at 100
        offset = (page - 1) * per_page

        # Build filter conditions
        conditions = []

        if status_filter:
            conditions.append(MergeRequestHistoryModel.status == status_filter)

        if date_from:
            conditions.append(MergeRequestHistoryModel.finished_at >= date_from.isoformat())

        if date_to:
            # Include full day
            date_to_end = datetime.combine(date_to, datetime.max.time())
            conditions.append(MergeRequestHistoryModel.finished_at <= date_to_end.isoformat())

        if author_username:
            conditions.append(MergeRequestHistoryModel.author_username == author_username)

        # Get total count
        count_stmt = select(func.count()).select_from(MergeRequestHistoryModel)
        if conditions:
            count_stmt = count_stmt.where(and_(*conditions))

        total_result = await self._session.execute(count_stmt)
        total = total_result.scalar() or 0

        # Get paginated items
        items_stmt = (
            select(MergeRequestHistoryModel)
            .order_by(MergeRequestHistoryModel.finished_at.desc())
            .offset(offset)
            .limit(per_page)
        )
        if conditions:
            items_stmt = items_stmt.where(and_(*conditions))

        items_result = await self._session.execute(items_stmt)
        items = items_result.scalars().all()

        total_pages = (total + per_page - 1) // per_page if total > 0 else 1

        return PaginatedResult(
            items=items,
            total=total,
            page=page,
            per_page=per_page,
            total_pages=total_pages,
        )

    async def get_by_iid(self, iid: int) -> MergeRequestHistoryModel | None:
        """Get a history entry by MR IID.

        Args:
            iid: The MR's internal ID.

        Returns:
            MergeRequestHistoryModel if found, None otherwise.
        """
        stmt = select(MergeRequestHistoryModel).where(MergeRequestHistoryModel.iid == iid)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_recent(self, limit: int = 10) -> Sequence[MergeRequestHistoryModel]:
        """Get most recent history entries."""
        stmt = select(MergeRequestHistoryModel).order_by(MergeRequestHistoryModel.finished_at.desc()).limit(limit)
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def get_stats_for_period(
        self,
        date_from: date,
        date_to: date,
    ) -> PeriodStats:
        """Get aggregate statistics for a date range.

        Args:
            date_from: Start date (inclusive).
            date_to: End date (inclusive).

        Returns:
            PeriodStats with counts and averages.
        """
        date_from_str = date_from.isoformat()
        date_to_str = datetime.combine(date_to, datetime.max.time()).isoformat()

        # Use CASE WHEN for SQLite compatibility (no IIF in older versions)
        stmt = select(
            func.count().label("total"),
            func.sum(case((MergeRequestHistoryModel.status == "merged", 1), else_=0)).label("success"),
            func.sum(case((MergeRequestHistoryModel.status == "failed", 1), else_=0)).label("failed"),
            func.sum(case((MergeRequestHistoryModel.status == "conflict", 1), else_=0)).label("conflict"),
            func.sum(case((MergeRequestHistoryModel.status == "timeout", 1), else_=0)).label("timeout"),
            func.sum(case((MergeRequestHistoryModel.is_hotfix == 1, 1), else_=0)).label("hotfix"),
            func.avg(MergeRequestHistoryModel.wait_time_seconds).label("avg_wait"),
            func.avg(MergeRequestHistoryModel.processing_time_seconds).label("avg_processing"),
        ).where(
            and_(
                MergeRequestHistoryModel.finished_at >= date_from_str,
                MergeRequestHistoryModel.finished_at <= date_to_str,
            )
        )

        result = await self._session.execute(stmt)
        row = result.one()

        return PeriodStats(
            total_processed=row.total or 0,
            success_count=row.success or 0,
            failed_count=row.failed or 0,
            conflict_count=row.conflict or 0,
            timeout_count=row.timeout or 0,
            hotfix_count=row.hotfix or 0,
            avg_wait_time_seconds=float(row.avg_wait) if row.avg_wait else None,
            avg_processing_time_seconds=(float(row.avg_processing) if row.avg_processing else None),
        )

    async def get_stats_for_date(self, target_date: date) -> PeriodStats:
        """Get statistics for a single date."""
        return await self.get_stats_for_period(target_date, target_date)

    async def get_stats_for_last_hour(self) -> PeriodStats:
        """Get aggregate statistics for the last hour.

        Queries MRs with finished_at in the last 60 minutes.
        Used by hourly snapshot job.

        Returns:
            PeriodStats with counts and averages for last hour.
        """
        now = datetime.now(UTC)
        hour_ago = now - timedelta(hours=1)

        stmt = select(
            func.count().label("total"),
            func.sum(case((MergeRequestHistoryModel.status == "merged", 1), else_=0)).label("success"),
            func.sum(
                case(
                    (
                        MergeRequestHistoryModel.status.in_(["failed", "conflict", "timeout"]),
                        1,
                    ),
                    else_=0,
                )
            ).label("failed"),
            func.avg(MergeRequestHistoryModel.wait_time_seconds).label("avg_wait"),
        ).where(
            and_(
                MergeRequestHistoryModel.finished_at >= hour_ago.isoformat(),
                MergeRequestHistoryModel.finished_at <= now.isoformat(),
            )
        )

        result = await self._session.execute(stmt)
        row = result.one()

        return PeriodStats(
            total_processed=row.total or 0,
            success_count=row.success or 0,
            failed_count=row.failed or 0,
            conflict_count=0,
            timeout_count=0,
            hotfix_count=0,
            avg_wait_time_seconds=float(row.avg_wait) if row.avg_wait else None,
            avg_processing_time_seconds=None,
        )

    async def cleanup_old_records(self, retention_days: int = 365) -> int:
        """Delete records older than retention period.

        Returns number of records deleted.
        """
        cutoff = datetime.now(UTC) - timedelta(days=retention_days)
        cutoff_str = cutoff.isoformat()

        stmt = delete(MergeRequestHistoryModel).where(MergeRequestHistoryModel.finished_at < cutoff_str)
        result = await self._session.execute(stmt)
        await self._session.flush()

        deleted_count: int = result.rowcount  # type: ignore[attr-defined]
        return deleted_count


# =============================================================================
# AnalyticsRepository
# =============================================================================


class AnalyticsRepository:
    """Repository for analytics data (hourly and daily).

    Handles snapshots, aggregation, and metrics retrieval.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save_hourly_snapshot(
        self,
        queue_depth: int,
        processed_count: int,
        success_count: int,
        failed_count: int,
        avg_wait_time_seconds: int | None,
    ) -> AnalyticsHourlyModel:
        """Save hourly queue snapshot.

        Timestamp is truncated to the hour.
        """
        now = datetime.now(UTC)
        timestamp = now.replace(minute=0, second=0, microsecond=0).isoformat()

        snapshot = AnalyticsHourlyModel(
            timestamp=timestamp,
            queue_depth=queue_depth,
            processed_count=processed_count,
            success_count=success_count,
            failed_count=failed_count,
            avg_wait_time_seconds=avg_wait_time_seconds,
        )

        self._session.add(snapshot)
        await self._session.flush()

        log.debug("Hourly snapshot saved", timestamp=timestamp, queue_depth=queue_depth)
        return snapshot

    async def aggregate_daily(self, target_date: date) -> AnalyticsDailyModel | None:
        """Aggregate hourly data into daily statistics.

        Args:
            target_date: Date to aggregate.

        Returns:
            AnalyticsDailyModel if created, None if already exists.
        """
        # Check if already aggregated
        existing_stmt = select(AnalyticsDailyModel).where(AnalyticsDailyModel.date == target_date.isoformat())
        existing_result = await self._session.execute(existing_stmt)
        if existing_result.scalar_one_or_none():
            log.debug("Daily stats already exist", date=target_date.isoformat())
            return None

        # Get stats from history for that date
        date_start = datetime.combine(target_date, datetime.min.time()).isoformat()
        date_end = datetime.combine(target_date, datetime.max.time()).isoformat()

        # Query history for the day
        history_stmt = select(
            func.count().label("total"),
            func.sum(case((MergeRequestHistoryModel.status == "merged", 1), else_=0)).label("success"),
            func.sum(case((MergeRequestHistoryModel.status == "failed", 1), else_=0)).label("failed"),
            func.sum(case((MergeRequestHistoryModel.status == "conflict", 1), else_=0)).label("conflict"),
            func.sum(case((MergeRequestHistoryModel.status == "timeout", 1), else_=0)).label("timeout"),
            func.sum(case((MergeRequestHistoryModel.is_hotfix == 1, 1), else_=0)).label("hotfix"),
            func.avg(MergeRequestHistoryModel.wait_time_seconds).label("avg_wait"),
            func.avg(MergeRequestHistoryModel.processing_time_seconds).label("avg_processing"),
        ).where(
            and_(
                MergeRequestHistoryModel.finished_at >= date_start,
                MergeRequestHistoryModel.finished_at <= date_end,
            )
        )

        history_result = await self._session.execute(history_stmt)
        history_row = history_result.one()

        # Get max queue depth from hourly snapshots
        hourly_stmt = select(func.max(AnalyticsHourlyModel.queue_depth)).where(
            and_(
                AnalyticsHourlyModel.timestamp >= date_start,
                AnalyticsHourlyModel.timestamp <= date_end,
            )
        )
        hourly_result = await self._session.execute(hourly_stmt)
        max_queue_depth = hourly_result.scalar()

        # Create daily record
        daily = AnalyticsDailyModel(
            date=target_date.isoformat(),
            total_processed=history_row.total or 0,
            success_count=history_row.success or 0,
            failed_count=history_row.failed or 0,
            conflict_count=history_row.conflict or 0,
            timeout_count=history_row.timeout or 0,
            hotfix_count=history_row.hotfix or 0,
            avg_wait_time_seconds=(int(history_row.avg_wait) if history_row.avg_wait else None),
            avg_processing_time_seconds=(int(history_row.avg_processing) if history_row.avg_processing else None),
            max_queue_depth=max_queue_depth,
        )

        self._session.add(daily)
        await self._session.flush()

        log.info(
            "Daily stats aggregated",
            date=target_date.isoformat(),
            total=daily.total_processed,
        )
        return daily

    async def get_metrics(self, period_days: int = 7) -> DashboardMetrics:
        """Get metrics for dashboard display.

        Args:
            period_days: Number of days to include in statistics.

        Returns:
            DashboardMetrics with current and historical data.
        """
        now = datetime.now(UTC)
        period_start = now - timedelta(days=period_days)
        period_start_str = period_start.isoformat()

        # Get current queue count
        queue_stmt = (
            select(func.count()).select_from(MergeRequestModel).where(MergeRequestModel.status.in_(ACTIVE_STATES))
        )
        queue_result = await self._session.execute(queue_stmt)
        total_in_queue = queue_result.scalar() or 0

        # Get period stats from history
        history_stmt = select(
            func.sum(case((MergeRequestHistoryModel.status == "merged", 1), else_=0)).label("merged"),
            func.sum(
                case(
                    (
                        MergeRequestHistoryModel.status.in_(("failed", "conflict", "timeout")),
                        1,
                    ),
                    else_=0,
                )
            ).label("failed"),
            func.avg(MergeRequestHistoryModel.wait_time_seconds).label("avg_wait"),
            func.avg(MergeRequestHistoryModel.processing_time_seconds).label("avg_processing"),
        ).where(MergeRequestHistoryModel.finished_at >= period_start_str)

        history_result = await self._session.execute(history_stmt)
        history_row = history_result.one()

        merged_count = history_row.merged or 0
        failed_count = history_row.failed or 0
        total_completed = merged_count + failed_count
        success_rate = (merged_count / total_completed * 100) if total_completed > 0 else 0.0

        # Get hourly trend (last 24 hours)
        hourly_start = (now - timedelta(hours=24)).isoformat()
        hourly_stmt = (
            select(AnalyticsHourlyModel)
            .where(AnalyticsHourlyModel.timestamp >= hourly_start)
            .order_by(AnalyticsHourlyModel.timestamp.asc())
        )
        hourly_result = await self._session.execute(hourly_stmt)
        hourly_records = hourly_result.scalars().all()

        hourly_trend = [
            {
                "timestamp": h.timestamp,
                "queue_depth": h.queue_depth,
                "processed_count": h.processed_count,
            }
            for h in hourly_records
        ]

        # Get daily stats (last 7 days)
        daily_start = (now - timedelta(days=7)).date().isoformat()
        daily_stmt = (
            select(AnalyticsDailyModel)
            .where(AnalyticsDailyModel.date >= daily_start)
            .order_by(AnalyticsDailyModel.date.asc())
        )
        daily_result = await self._session.execute(daily_stmt)
        daily_records = daily_result.scalars().all()

        daily_stats = [
            {
                "date": d.date,
                "total_processed": d.total_processed,
                "success_count": d.success_count,
                "failed_count": d.failed_count,
            }
            for d in daily_records
        ]

        return DashboardMetrics(
            total_in_queue=total_in_queue,
            merged_count=merged_count,
            failed_count=failed_count,
            success_rate=round(success_rate, 1),
            avg_wait_seconds=round(float(history_row.avg_wait or 0), 1),
            avg_processing_seconds=round(float(history_row.avg_processing or 0), 1),
            hourly_trend=hourly_trend,
            daily_stats=daily_stats,
        )

    async def cleanup_hourly(self, retention_days: int = 30) -> int:
        """Delete hourly records older than retention period."""
        cutoff = datetime.now(UTC) - timedelta(days=retention_days)
        cutoff_str = cutoff.isoformat()

        stmt = delete(AnalyticsHourlyModel).where(AnalyticsHourlyModel.timestamp < cutoff_str)
        result = await self._session.execute(stmt)
        await self._session.flush()

        deleted_count: int = result.rowcount  # type: ignore[attr-defined]
        return deleted_count

    async def get_max_queue_depth_for_date(self, target_date: date) -> int | None:
        """Get maximum queue depth from hourly snapshots for a date."""
        date_start = datetime.combine(target_date, datetime.min.time()).isoformat()
        date_end = datetime.combine(target_date, datetime.max.time()).isoformat()

        stmt = select(func.max(AnalyticsHourlyModel.queue_depth)).where(
            and_(
                AnalyticsHourlyModel.timestamp >= date_start,
                AnalyticsHourlyModel.timestamp <= date_end,
            )
        )
        result = await self._session.execute(stmt)
        return result.scalar()


# =============================================================================
# UnitOfWork
# =============================================================================


class UnitOfWork:
    """Unit of Work pattern for managing transactions across repositories.

    Provides a single transaction boundary for operations that span
    multiple repositories, ensuring atomicity.

    Example:
        >>> async with UnitOfWork(db) as uow:
        ...     mr = await uow.merge_requests.get_by_iid(42)
        ...     await uow.merge_requests.complete_mr(42, "merged")
        ...     await uow.commit()

    Example with auto-commit:
        >>> async with UnitOfWork(db, auto_commit=True) as uow:
        ...     await uow.merge_requests.update_status(42, "testing")
        ...     # Commits automatically on successful exit
    """

    def __init__(
        self,
        db: Database,
        auto_commit: bool = False,
    ) -> None:
        """Initialize Unit of Work.

        Args:
            db: Database instance for session management.
            auto_commit: If True, auto-commit on successful exit.
        """
        self._db = db
        self._auto_commit = auto_commit
        self._session: AsyncSession | None = None
        self._session_context: Any = None

        # Lazy-initialized repositories
        self._merge_requests: MergeRequestRepository | None = None
        self._history: HistoryRepository | None = None
        self._analytics: AnalyticsRepository | None = None

    async def __aenter__(self) -> UnitOfWork:
        """Enter transaction context."""
        # Use db.transaction() for auto-commit or db.session() for manual
        if self._auto_commit:
            self._session_context = self._db.transaction()
        else:
            self._session_context = self._db.session()

        self._session = await self._session_context.__aenter__()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        """Exit transaction context."""
        await self._session_context.__aexit__(exc_type, exc_val, exc_tb)
        self._session = None
        self._merge_requests = None
        self._history = None
        self._analytics = None

    @property
    def session(self) -> AsyncSession:
        """Get current session."""
        if self._session is None:
            raise RuntimeError("UnitOfWork must be used as async context manager")
        return self._session

    @property
    def merge_requests(self) -> MergeRequestRepository:
        """Get MergeRequest repository."""
        if self._merge_requests is None:
            self._merge_requests = MergeRequestRepository(self.session)
        return self._merge_requests

    @property
    def history(self) -> HistoryRepository:
        """Get History repository."""
        if self._history is None:
            self._history = HistoryRepository(self.session)
        return self._history

    @property
    def analytics(self) -> AnalyticsRepository:
        """Get Analytics repository."""
        if self._analytics is None:
            self._analytics = AnalyticsRepository(self.session)
        return self._analytics

    async def commit(self) -> None:
        """Commit the current transaction."""
        await self.session.commit()

    async def rollback(self) -> None:
        """Rollback the current transaction."""
        await self.session.rollback()


# =============================================================================
# ModelConverter
# =============================================================================


class ModelConverter:
    """Convert between ORM models and domain objects."""

    @staticmethod
    def mr_model_to_queue_item(mr: MergeRequestModel) -> QueueItem:
        """Convert MergeRequestModel to QueueItem dataclass."""
        from gitlab_queue.models.queue_item import QueueItem as QI

        queued_at = datetime.fromisoformat(mr.queued_at) if mr.queued_at else datetime.now(UTC)
        started_at = datetime.fromisoformat(mr.started_at) if mr.started_at else None
        finished_at = datetime.fromisoformat(mr.finished_at) if mr.finished_at else None

        labels: list[str] = []
        if mr.labels:
            try:
                labels = json.loads(mr.labels)
            except (json.JSONDecodeError, TypeError):
                labels = []

        return QI(
            mr_iid=mr.iid,
            title=mr.title,
            author_name=mr.author_name,
            author_username=mr.author_username,
            target_branch=mr.target_branch,
            state=mr.status,
            queued_at=queued_at,
            project_id=mr.project_id,
            is_hotfix=bool(mr.is_hotfix),
            author_avatar=mr.author_avatar,
            labels=labels,
            started_at=started_at,
            finished_at=finished_at,
            pipeline_id=mr.pipeline_id,
            pipeline_status=mr.pipeline_status,
            retry_count=mr.retry_count or 0,
            last_error=mr.last_error,
            stale_warning_sent=bool(mr.stale_warning_sent),
        )

    @staticmethod
    def history_model_to_queue_item(history: MergeRequestHistoryModel) -> QueueItem:
        """Convert MergeRequestHistoryModel to QueueItem for display."""
        from gitlab_queue.models.queue_item import QueueItem as QI

        queued_at = datetime.fromisoformat(history.queued_at) if history.queued_at else datetime.now(UTC)
        started_at = datetime.fromisoformat(history.started_at) if history.started_at else None
        finished_at = datetime.fromisoformat(history.finished_at) if history.finished_at else None

        labels: list[str] = []
        if history.labels:
            try:
                labels = json.loads(history.labels)
            except (json.JSONDecodeError, TypeError):
                labels = []

        return QI(
            mr_iid=history.iid,
            title=history.title,
            author_name=history.author_name,
            author_username=history.author_username,
            target_branch=history.target_branch,
            state=history.status,
            queued_at=queued_at,
            project_id=history.project_id,
            is_hotfix=bool(history.is_hotfix),
            author_avatar=history.author_avatar,
            labels=labels,
            started_at=started_at,
            finished_at=finished_at,
            pipeline_id=history.pipeline_id,
            pipeline_status=history.pipeline_status,
            retry_count=0,
            last_error=history.failure_reason,
            stale_warning_sent=False,
        )


# =============================================================================
# Exports
# =============================================================================

__all__: list[str] = [
    # Constants
    "ACTIVE_STATES",
    "TERMINAL_STATES",
    "AnalyticsRepository",
    # Data classes
    "CompleteMRResult",
    "DashboardMetrics",
    "DuplicateRecordError",
    "HistoryRepository",
    "MergeRequestNotFoundError",
    # Repositories
    "MergeRequestRepository",
    # Converters
    "ModelConverter",
    "PaginatedResult",
    "PeriodStats",
    # Exceptions
    "RepositoryError",
    # Unit of Work
    "UnitOfWork",
]
