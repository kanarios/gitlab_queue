"""Test that hourly snapshot records current queue state.

Covers _save_hourly_snapshot (lines 149-158):
- Gets current queue depth from merge_requests.count_active()
- Gets stats from history.get_stats_for_last_hour()
- Saves snapshot via analytics.save_hourly_snapshot()
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import vedro

from gitlab_queue.jobs.analytics import AnalyticsJobProcessor


class Scenario(vedro.Scenario):
    subject = "hourly snapshot records current queue state"

    def given_analytics_processor_with_mocked_database(self):
        self.database = MagicMock()
        self.settings = MagicMock()

        # Mock UnitOfWork context manager
        self.mock_uow = MagicMock()
        self.mock_uow.__aenter__ = AsyncMock(return_value=self.mock_uow)
        self.mock_uow.__aexit__ = AsyncMock(return_value=None)

        # Mock repository methods
        self.mock_uow.merge_requests = MagicMock()
        self.mock_uow.merge_requests.count_active = AsyncMock(return_value=5)

        self.mock_stats = MagicMock()
        self.mock_stats.total_processed = 10
        self.mock_stats.success_count = 8
        self.mock_stats.failed_count = 2
        self.mock_stats.avg_wait_time_seconds = 120.5

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

    def then_queue_depth_was_fetched(self):
        self.mock_uow.merge_requests.count_active.assert_called_once()

    def and_hourly_stats_were_fetched(self):
        self.mock_uow.history.get_stats_for_last_hour.assert_called_once()

    def and_snapshot_was_saved_with_correct_data(self):
        self.mock_uow.analytics.save_hourly_snapshot.assert_called_once_with(
            queue_depth=5,
            processed_count=10,
            success_count=8,
            failed_count=2,
            avg_wait_time_seconds=120,
        )
