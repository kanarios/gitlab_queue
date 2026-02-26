"""Test that cleanup removes data older than retention period.

Covers _cleanup_hourly_analytics (lines 205-238):
- Calls analytics.cleanup_hourly(retention_days)
- Runs VACUUM when records are deleted
- No VACUUM when nothing to clean up

Also covers _cleanup_history for 1-year retention.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import vedro

from gitlab_queue.jobs.analytics import AnalyticsJobProcessor


class Scenario(vedro.Scenario):
    subject = "cleanup removes hourly analytics older than 30 days and runs vacuum"

    def given_analytics_processor_with_old_data(self):
        """
        Prepare the test fixture with an AnalyticsJobProcessor and mocks that simulate existing old hourly analytics data.

        Sets:
        - self.database and self.settings as MagicMock instances.
        - self.mock_uow as an async context manager mock whose .analytics.cleanup_hourly coroutine returns 150.
        - self.processor as an AnalyticsJobProcessor configured with the mocked database and settings and with ._vacuum_database replaced by an AsyncMock.
        """
        self.database = MagicMock()
        self.settings = MagicMock()

        self.mock_uow = MagicMock()
        self.mock_uow.__aenter__ = AsyncMock(return_value=self.mock_uow)
        self.mock_uow.__aexit__ = AsyncMock(return_value=None)

        self.mock_uow.analytics = MagicMock()
        self.mock_uow.analytics.cleanup_hourly = AsyncMock(return_value=150)

        self.processor = AnalyticsJobProcessor(
            database=self.database,
            settings=self.settings,
        )
        self.processor._vacuum_database = AsyncMock()

    async def when_cleanup_hourly_analytics_is_called(self):
        with patch(
            "gitlab_queue.jobs.analytics.UnitOfWork",
            return_value=self.mock_uow,
        ):
            await self.processor._cleanup_hourly_analytics()

    def then_cleanup_was_called_with_30_day_retention(self):
        """
        Asserts that the analytics hourly cleanup was invoked once with a 30-day retention.

        Raises an assertion error if cleanup_hourly was not awaited exactly once with the argument 30.
        """
        self.mock_uow.analytics.cleanup_hourly.assert_awaited_once_with(30)

    def and_vacuum_was_triggered(self):
        """
        Asserts that the processor triggered a single database vacuum operation.

        Raises an AssertionError if the processor's _vacuum_database coroutine was not awaited exactly once.
        """
        self.processor._vacuum_database.assert_awaited_once()


class Scenario2(vedro.Scenario):
    subject = "cleanup skips vacuum when no records are deleted"

    def given_analytics_processor_with_no_old_data(self):
        self.database = MagicMock()
        self.settings = MagicMock()

        self.mock_uow = MagicMock()
        self.mock_uow.__aenter__ = AsyncMock(return_value=self.mock_uow)
        self.mock_uow.__aexit__ = AsyncMock(return_value=None)

        self.mock_uow.analytics = MagicMock()
        self.mock_uow.analytics.cleanup_hourly = AsyncMock(return_value=0)

        self.processor = AnalyticsJobProcessor(
            database=self.database,
            settings=self.settings,
        )
        self.processor._vacuum_database = AsyncMock()

    async def when_cleanup_hourly_analytics_is_called(self):
        with patch(
            "gitlab_queue.jobs.analytics.UnitOfWork",
            return_value=self.mock_uow,
        ):
            await self.processor._cleanup_hourly_analytics()

    def then_cleanup_was_called(self):
        """
        Assert that hourly analytics cleanup was awaited exactly once with a 30-day retention.

        Raises:
            AssertionError: If `analytics.cleanup_hourly` was not awaited exactly once with the argument 30.
        """
        self.mock_uow.analytics.cleanup_hourly.assert_awaited_once_with(30)

    def and_vacuum_was_not_triggered(self):
        self.processor._vacuum_database.assert_not_awaited()


class Scenario3(vedro.Scenario):
    subject = "history cleanup removes records older than 365 days"

    def given_analytics_processor_with_old_history(self):
        self.database = MagicMock()
        self.settings = MagicMock()

        self.mock_uow = MagicMock()
        self.mock_uow.__aenter__ = AsyncMock(return_value=self.mock_uow)
        self.mock_uow.__aexit__ = AsyncMock(return_value=None)

        self.mock_uow.history = MagicMock()
        self.mock_uow.history.cleanup_old_records = AsyncMock(return_value=50)

        self.processor = AnalyticsJobProcessor(
            database=self.database,
            settings=self.settings,
        )
        self.processor._vacuum_database = AsyncMock()

    async def when_cleanup_history_is_called(self):
        with patch(
            "gitlab_queue.jobs.analytics.UnitOfWork",
            return_value=self.mock_uow,
        ):
            await self.processor._cleanup_history()

    def then_cleanup_was_called_with_365_day_retention(self):
        """
        Asserts that history.cleanup_old_records was awaited exactly once with a 365-day retention.

        Raises:
                AssertionError: If the mocked method was not awaited exactly once with the value 365.
        """
        self.mock_uow.history.cleanup_old_records.assert_awaited_once_with(365)

    def and_vacuum_was_triggered(self):
        """
        Asserts that the processor triggered a single database vacuum operation.

        Raises an AssertionError if the processor's _vacuum_database coroutine was not awaited exactly once.
        """
        self.processor._vacuum_database.assert_awaited_once()
