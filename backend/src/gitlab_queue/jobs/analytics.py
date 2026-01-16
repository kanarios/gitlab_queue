"""Analytics and Data Retention Jobs for GitLab Merge Queue Bot.

Provides scheduled jobs for:
- Hourly queue snapshots (every hour at :00)
- Daily statistics aggregation (every day at 00:05)
- Hourly analytics cleanup (30-day retention, daily at 01:00)
- History cleanup (1-year retention, monthly on 1st at 02:00)

Uses APScheduler for cron-like scheduling with graceful shutdown support.

Example:
    >>> processor = AnalyticsJobProcessor(database=db, settings=settings)
    >>> task = asyncio.create_task(processor.run())
    >>> # ... later
    >>> processor.request_shutdown()
    >>> await task
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import TYPE_CHECKING

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import text

from gitlab_queue.db import Database, UnitOfWork
from gitlab_queue.utils.logging import get_logger

if TYPE_CHECKING:
    from gitlab_queue.config import Settings

log = get_logger(__name__)


@dataclass
class AnalyticsJobProcessor:
    """Background processor for analytics and data retention jobs.

    Manages APScheduler lifecycle and provides graceful shutdown.

    Attributes:
        database: Database instance for data access.
        settings: Application settings.

    Example:
        >>> processor = AnalyticsJobProcessor(database=db, settings=settings)
        >>> task = asyncio.create_task(processor.run())
        >>> # ... later
        >>> processor.request_shutdown()
        >>> await task
    """

    database: Database
    settings: Settings

    # Internal state
    _shutdown_event: asyncio.Event = field(default_factory=asyncio.Event, init=False)
    _scheduler: AsyncIOScheduler | None = field(default=None, init=False)

    async def run(self) -> None:
        """Main loop - starts scheduler and waits for shutdown."""
        log.info("Analytics job processor starting")

        try:
            self._scheduler = AsyncIOScheduler(timezone="UTC")
            self._configure_jobs()
            self._scheduler.start()

            log.info(
                "Analytics scheduler started",
                job_count=len(self._scheduler.get_jobs()),
            )

            # Wait for shutdown signal
            await self._shutdown_event.wait()

        finally:
            if self._scheduler:
                self._scheduler.shutdown(wait=False)
            log.info("Analytics job processor stopped")

    def _configure_jobs(self) -> None:
        """Configure all scheduled jobs."""
        if self._scheduler is None:
            return

        # Hourly snapshot: every hour at :00
        self._scheduler.add_job(
            self._save_hourly_snapshot,
            CronTrigger(minute=0),
            id="hourly_snapshot",
            name="Save hourly queue snapshot",
            replace_existing=True,
        )

        # Daily aggregation: every day at 00:05
        self._scheduler.add_job(
            self._aggregate_daily_stats,
            CronTrigger(hour=0, minute=5),
            id="daily_aggregation",
            name="Aggregate daily statistics",
            replace_existing=True,
        )

        # Hourly cleanup: every day at 01:00 (30-day retention)
        self._scheduler.add_job(
            self._cleanup_hourly_analytics,
            CronTrigger(hour=1, minute=0),
            id="hourly_cleanup",
            name="Cleanup old hourly analytics",
            replace_existing=True,
        )

        # History cleanup: 1st of month at 02:00 (1-year retention)
        self._scheduler.add_job(
            self._cleanup_history,
            CronTrigger(day=1, hour=2, minute=0),
            id="history_cleanup",
            name="Cleanup old MR history",
            replace_existing=True,
        )

        log.debug(
            "Configured analytics jobs",
            jobs=[job.id for job in self._scheduler.get_jobs()],
        )

    async def _save_hourly_snapshot(self) -> None:
        """Save hourly queue snapshot.

        Collects:
        - Current queue depth (active MRs)
        - Processed count in last hour
        - Success/failure counts in last hour
        - Average wait time for completed MRs
        """
        log.debug("Running hourly snapshot job")

        try:
            async with UnitOfWork(self.database, auto_commit=True) as uow:
                # Get current queue depth
                queue_depth = await uow.merge_requests.count_active()

                # Get stats for last hour from history
                stats = await uow.history.get_stats_for_last_hour()

                # Save snapshot
                await uow.analytics.save_hourly_snapshot(
                    queue_depth=queue_depth,
                    processed_count=stats.total_processed,
                    success_count=stats.success_count,
                    failed_count=stats.failed_count,
                    avg_wait_time_seconds=(int(stats.avg_wait_time_seconds) if stats.avg_wait_time_seconds else None),
                )

            log.info(
                "Hourly snapshot saved",
                queue_depth=queue_depth,
                processed_count=stats.total_processed,
            )

        except Exception:
            log.exception("Failed to save hourly snapshot")

    async def _aggregate_daily_stats(self) -> None:
        """Aggregate yesterday's statistics into daily table."""
        yesterday = date.today() - timedelta(days=1)

        log.debug("Running daily aggregation job", target_date=yesterday.isoformat())

        try:
            async with UnitOfWork(self.database, auto_commit=True) as uow:
                result = await uow.analytics.aggregate_daily(yesterday)

                if result:
                    log.info(
                        "Daily stats aggregated",
                        date=yesterday.isoformat(),
                        total_processed=result.total_processed,
                    )
                else:
                    log.debug(
                        "Daily stats already exist",
                        date=yesterday.isoformat(),
                    )

        except Exception:
            log.exception(
                "Failed to aggregate daily stats",
                date=yesterday.isoformat(),
            )

    async def _cleanup_hourly_analytics(self) -> None:
        """Cleanup hourly analytics older than 30 days."""
        retention_days = 30

        log.debug("Running hourly analytics cleanup", retention_days=retention_days)

        try:
            async with UnitOfWork(self.database, auto_commit=True) as uow:
                deleted_count = await uow.analytics.cleanup_hourly(retention_days)

            if deleted_count > 0:
                log.info(
                    "Hourly analytics cleanup completed",
                    deleted_count=deleted_count,
                    retention_days=retention_days,
                )
                # Run VACUUM after significant cleanup
                await self._vacuum_database()
            else:
                log.debug("No hourly analytics to cleanup")

        except Exception:
            log.exception("Failed to cleanup hourly analytics")

    async def _cleanup_history(self) -> None:
        """Cleanup MR history older than 1 year."""
        retention_days = 365

        log.debug("Running history cleanup", retention_days=retention_days)

        try:
            async with UnitOfWork(self.database, auto_commit=True) as uow:
                deleted_count = await uow.history.cleanup_old_records(retention_days)

            if deleted_count > 0:
                log.info(
                    "History cleanup completed",
                    deleted_count=deleted_count,
                    retention_days=retention_days,
                )
                # Run VACUUM after significant cleanup
                await self._vacuum_database()
            else:
                log.debug("No history records to cleanup")

        except Exception:
            log.exception("Failed to cleanup history")

    async def _vacuum_database(self) -> None:
        """Run VACUUM to reclaim space after deletions.

        Note: SQLite VACUUM requires exclusive access and cannot run
        inside a transaction. We use a raw connection for this.
        """
        log.debug("Running database VACUUM")

        try:
            # VACUUM must run outside transaction with autocommit
            async with self.database.engine.connect() as conn:
                # SQLite requires VACUUM outside transaction
                await conn.execute(text("VACUUM"))
                await conn.commit()

            log.info("Database VACUUM completed")

        except Exception:
            log.warning("Database VACUUM failed (non-critical)")

    def request_shutdown(self) -> None:
        """Request graceful shutdown of the processor."""
        log.info("Analytics processor shutdown requested")
        self._shutdown_event.set()

    @property
    def is_shutdown_requested(self) -> bool:
        """Check if shutdown has been requested."""
        return self._shutdown_event.is_set()


def create_analytics_processor(
    database: Database,
    settings: Settings,
) -> AnalyticsJobProcessor:
    """Create a configured AnalyticsJobProcessor instance.

    Args:
        database: Database instance.
        settings: Application settings.

    Returns:
        Configured AnalyticsJobProcessor ready to run.
    """
    return AnalyticsJobProcessor(
        database=database,
        settings=settings,
    )


__all__: list[str] = [
    "AnalyticsJobProcessor",
    "create_analytics_processor",
]
