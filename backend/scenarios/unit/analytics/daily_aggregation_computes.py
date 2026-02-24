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
        with patch(
            "gitlab_queue.jobs.analytics.UnitOfWork",
            return_value=self.mock_uow,
        ):
            await self.processor._aggregate_daily_stats()

    def then_aggregate_daily_was_called_with_yesterday(self):
        yesterday = date.today() - timedelta(days=1)
        self.mock_uow.analytics.aggregate_daily.assert_awaited_once_with(yesterday)


class Scenario2(vedro.Scenario):
    subject = "daily aggregation handles already-existing stats gracefully"

    def given_analytics_processor_where_daily_stats_already_exist(self):
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
        assert self.raised is False

    def and_aggregate_daily_was_still_called(self):
        self.mock_uow.analytics.aggregate_daily.assert_awaited_once()
