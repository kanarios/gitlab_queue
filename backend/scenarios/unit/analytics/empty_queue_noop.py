"""Test that analytics operations are no-op when queue is empty.

Covers _save_hourly_snapshot with zero queue depth and zero stats,
and verifies that exceptions in the snapshot job are caught.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import vedro

from gitlab_queue.jobs.analytics import AnalyticsJobProcessor


class Scenario(vedro.Scenario):
    subject = "hourly snapshot saves zero counts when queue is empty"

    def given_analytics_processor_with_empty_queue(self):
        self.database = MagicMock()
        self.settings = MagicMock()

        self.mock_uow = MagicMock()
        self.mock_uow.__aenter__ = AsyncMock(return_value=self.mock_uow)
        self.mock_uow.__aexit__ = AsyncMock(return_value=None)

        self.mock_uow.merge_requests = MagicMock()
        self.mock_uow.merge_requests.count_active = AsyncMock(return_value=0)

        self.mock_stats = MagicMock()
        self.mock_stats.total_processed = 0
        self.mock_stats.success_count = 0
        self.mock_stats.failed_count = 0
        self.mock_stats.avg_wait_time_seconds = None

        self.mock_uow.history = MagicMock()
        self.mock_uow.history.get_stats_for_last_hour = AsyncMock(
            return_value=self.mock_stats,
        )

        self.mock_uow.analytics = MagicMock()
        self.mock_uow.analytics.save_hourly_snapshot = AsyncMock()

        self.processor = AnalyticsJobProcessor(
            database=self.database,
            settings=self.settings,
        )

    async def when_save_hourly_snapshot_is_called(self):
        with patch(
            "gitlab_queue.jobs.analytics.UnitOfWork",
            return_value=self.mock_uow,
        ):
            await self.processor._save_hourly_snapshot()

    def then_snapshot_was_saved_with_zero_values(self):
        self.mock_uow.analytics.save_hourly_snapshot.assert_called_once_with(
            queue_depth=0,
            processed_count=0,
            success_count=0,
            failed_count=0,
            avg_wait_time_seconds=None,
        )


class Scenario2(vedro.Scenario):
    subject = "hourly snapshot catches exception and does not propagate"

    def given_analytics_processor_where_database_raises(self):
        self.database = MagicMock()
        self.settings = MagicMock()

        self.mock_uow = MagicMock()
        self.mock_uow.__aenter__ = AsyncMock(
            side_effect=RuntimeError("Database connection lost"),
        )
        self.mock_uow.__aexit__ = AsyncMock(return_value=None)

        self.processor = AnalyticsJobProcessor(
            database=self.database,
            settings=self.settings,
        )

    async def when_save_hourly_snapshot_is_called(self):
        with patch(
            "gitlab_queue.jobs.analytics.UnitOfWork",
            return_value=self.mock_uow,
        ):
            self.raised = False
            try:
                await self.processor._save_hourly_snapshot()
            except Exception:
                self.raised = True

    def then_no_exception_is_propagated(self):
        assert self.raised is False
