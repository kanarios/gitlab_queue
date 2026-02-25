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
        """
        Prepare an AnalyticsJobProcessor and related mocks for testing hourly snapshot persistence.
        
        Sets up:
        - self.database and self.settings as MagicMocks.
        - self.mock_uow as an async context manager that is returned by UnitOfWork.
        - self.mock_uow.merge_requests.count_active to return 5.
        - self.mock_stats with total_processed=10, success_count=8, failed_count=2, avg_wait_time_seconds=120.5 and self.mock_uow.history.get_stats_for_last_hour to return it.
        - self.mock_uow.analytics.save_hourly_snapshot as an AsyncMock.
        - self.processor as an AnalyticsJobProcessor instantiated with the mocked database and settings.
        """
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
        """
        Runs the processor's hourly snapshot routine while patching UnitOfWork to use the test's mocked unit of work.
        
        Patches gitlab_queue.jobs.analytics.UnitOfWork to return self.mock_uow and then calls self.processor._save_hourly_snapshot() to exercise fetching queue depth, retrieving last-hour stats, and saving the hourly snapshot.
        """
        with patch(
            "gitlab_queue.jobs.analytics.UnitOfWork",
            return_value=self.mock_uow,
        ):
            await self.processor._save_hourly_snapshot()

    def then_queue_depth_was_fetched(self):
        """
        Assert that the current queue depth was fetched exactly once from the merge requests repository.
         
        Checks that `self.mock_uow.merge_requests.count_active` was awaited exactly one time.
        """
        self.mock_uow.merge_requests.count_active.assert_awaited_once()

    def and_hourly_stats_were_fetched(self):
        """
        Asserts that hourly statistics were fetched from the history repository exactly once.
        
        This verifies that history.get_stats_for_last_hour was awaited a single time on the mocked UnitOfWork.
        """
        self.mock_uow.history.get_stats_for_last_hour.assert_awaited_once()

    def and_snapshot_was_saved_with_correct_data(self):
        """
        Asserts that an hourly snapshot was saved once with the expected queue and metric values.
        
        Verifies that analytics.save_hourly_snapshot was awaited exactly once with:
        queue_depth=5, processed_count=10, success_count=8, failed_count=2, avg_wait_time_seconds=120.
        """
        self.mock_uow.analytics.save_hourly_snapshot.assert_awaited_once_with(
            queue_depth=5,
            processed_count=10,
            success_count=8,
            failed_count=2,
            avg_wait_time_seconds=120,
        )
