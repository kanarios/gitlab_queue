"""Test that daily aggregation computes summary stats.

Covers _aggregate_daily_stats (lines 175-189):
- Computes yesterday's date
- Calls analytics.aggregate_daily(yesterday)
- Logs result or 'already exists'
"""

from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import vedro

from gitlab_queue.jobs.analytics import AnalyticsJobProcessor


class Scenario(vedro.Scenario):
    subject = "daily aggregation computes summary stats for yesterday"

    def given_analytics_processor_with_mocked_database(self):
        """
        Set up a mocked AnalyticsJobProcessor and its test fixtures for daily aggregation.

        Creates and attaches to self:
        - database: MagicMock acting as the database dependency.
        - settings: MagicMock for configuration.
        - mock_uow: an async-capable MagicMock unit-of-work with __aenter__/__aexit__ implemented.
        - mock_result: MagicMock with total_processed set to 25.
        - mock_uow.analytics.aggregate_daily: AsyncMock that returns mock_result.
        - processor: AnalyticsJobProcessor instantiated with the mocked database and settings.

        This prepares the scenario where calling the processor's daily aggregation interacts with the mocked UnitOfWork and returns a predefined aggregation result.
        """
        self.database = MagicMock()
        self.settings = MagicMock()

        self.mock_uow = MagicMock()
        self.mock_uow.__aenter__ = AsyncMock(return_value=self.mock_uow)
        self.mock_uow.__aexit__ = AsyncMock(return_value=None)

        self.mock_result = MagicMock()
        self.mock_result.total_processed = 25

        self.mock_uow.analytics = MagicMock()
        self.mock_uow.analytics.aggregate_daily = AsyncMock(
            return_value=self.mock_result,
        )

        self.processor = AnalyticsJobProcessor(
            database=self.database,
            settings=self.settings,
        )

    async def when_aggregate_daily_stats_is_called(self):
        """
        Invoke AnalyticsJobProcessor._aggregate_daily_stats using the scenario's mocked UnitOfWork.

        Patches gitlab_queue.jobs.analytics.UnitOfWork to return self.mock_uow and awaits self.processor._aggregate_daily_stats().
        """
        with patch(
            "gitlab_queue.jobs.analytics.UnitOfWork",
            return_value=self.mock_uow,
        ):
            await self.processor._aggregate_daily_stats()

    def then_aggregate_daily_was_called_with_yesterday(self):
        """
        Assert that analytics.aggregate_daily was awaited once with yesterday's date.

        This verifies the test mock recorded a single await call to aggregate_daily using date.today() - 1 day.
        """
        yesterday = date.today() - timedelta(days=1)
        self.mock_uow.analytics.aggregate_daily.assert_awaited_once_with(yesterday)


class Scenario2(vedro.Scenario):
    subject = "daily aggregation handles already-existing stats gracefully"

    def given_analytics_processor_where_daily_stats_already_exist(self):
        """
        Set up an AnalyticsJobProcessor test fixture where daily aggregation reports that yesterday's stats already exist.

        Creates mocked database and settings, a mocked asynchronous unit-of-work context manager whose `analytics.aggregate_daily` coroutine returns `None` (simulating no new summary created), and instantiates `AnalyticsJobProcessor` with those mocks.
        """
        self.database = MagicMock()
        self.settings = MagicMock()

        self.mock_uow = MagicMock()
        self.mock_uow.__aenter__ = AsyncMock(return_value=self.mock_uow)
        self.mock_uow.__aexit__ = AsyncMock(return_value=None)

        self.mock_uow.analytics = MagicMock()
        self.mock_uow.analytics.aggregate_daily = AsyncMock(return_value=None)

        self.processor = AnalyticsJobProcessor(
            database=self.database,
            settings=self.settings,
        )

    async def when_aggregate_daily_stats_is_called(self):
        """
        Invoke AnalyticsJobProcessor._aggregate_daily_stats with UnitOfWork patched to the prepared mock and record whether it raised an exception.

        Sets self.raised to True if an exception is raised during the call, otherwise sets it to False.
        """
        with patch(
            "gitlab_queue.jobs.analytics.UnitOfWork",
            return_value=self.mock_uow,
        ):
            self.raised = False
            try:
                await self.processor._aggregate_daily_stats()
            except Exception:
                self.raised = True

    def then_no_exception_is_raised(self):
        """
        Assert that the scenario did not raise an exception.
        """
        assert self.raised is False

    def and_aggregate_daily_was_still_called(self):
        """
        Asserts that the mocked unit-of-work's analytics.aggregate_daily coroutine was awaited exactly once.
        """
        self.mock_uow.analytics.aggregate_daily.assert_awaited_once()
