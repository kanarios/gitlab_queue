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
        """
        Prepare an AnalyticsJobProcessor and supporting mocks that simulate an empty queue and zero activity.

        Configures:
        - a mocked UnitOfWork usable as an async context manager,
        - merge_requests.count_active to return 0,
        - history.get_stats_for_last_hour to return stats with total_processed=0, success_count=0, failed_count=0, avg_wait_time_seconds=None,
        - analytics.save_hourly_snapshot as an AsyncMock,
        and instantiates AnalyticsJobProcessor with the mocked database and settings.
        """
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
        """
        Invokes the processor's hourly snapshot routine with UnitOfWork patched to the prepared mock.

        Patches gitlab_queue.jobs.analytics.UnitOfWork to return self.mock_uow and awaits self.processor._save_hourly_snapshot().
        """
        with patch(
            "gitlab_queue.jobs.analytics.UnitOfWork",
            return_value=self.mock_uow,
        ):
            await self.processor._save_hourly_snapshot()

    def then_snapshot_was_saved_with_zero_values(self):
        self.mock_uow.analytics.save_hourly_snapshot.assert_awaited_once_with(
            queue_depth=0,
            processed_count=0,
            success_count=0,
            failed_count=0,
            avg_wait_time_seconds=None,
        )


class Scenario2(vedro.Scenario):
    subject = "hourly snapshot catches exception and does not propagate"

    def given_analytics_processor_where_database_raises(self):
        """
        Prepare an AnalyticsJobProcessor and supporting mocks where entering the UnitOfWork raises a RuntimeError.

        Creates MagicMock instances for database and settings, builds a mock unit-of-work whose __aenter__ raises RuntimeError("Database connection lost") and whose __aexit__ is an async no-op, and instantiates AnalyticsJobProcessor with the mocked database and settings.
        """
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
        """
        Calls the processor's _save_hourly_snapshot with UnitOfWork patched to the prepared mock and records whether an exception was raised into `self.raised`.

        This step patches `gitlab_queue.jobs.analytics.UnitOfWork` to return the scenario's `mock_uow`, invokes `self.processor._save_hourly_snapshot()`, and sets `self.raised` to `True` if the call raises an exception, otherwise `False`.
        """
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
        """
        Asserts that calling _save_hourly_snapshot did not raise an exception.

        Raises an AssertionError if an exception was propagated during the call.
        """
        assert self.raised is False
