"""Test that daily aggregation computes summary stats.

Covers _aggregate_daily_stats:
- Computes yesterday's date
- Calls analytics.aggregate_daily(yesterday)
- Logs result or 'already exists'
"""

from __future__ import annotations

from datetime import date, timedelta

import vedro

from gitlab_queue.jobs.analytics import AnalyticsJobProcessor
from scenarios.fakes import DailyAggregationResult, FakeUnitOfWork

_STUB = object()


class Scenario(vedro.Scenario):
    subject = "daily aggregation computes summary stats for yesterday"

    def given_analytics_processor_with_data(self):
        self.uow = FakeUnitOfWork()
        self.uow.analytics.aggregate_daily_result = DailyAggregationResult(
            total_processed=25,
        )

        self.processor = AnalyticsJobProcessor(
            database=_STUB,
            settings=_STUB,
            uow_factory=lambda *a, **kw: self.uow,
        )

    async def when_aggregate_daily_stats_is_called(self):
        self.yesterday = date.today() - timedelta(days=1)
        await self.processor._aggregate_daily_stats()

    def then_aggregate_daily_was_called_with_yesterday(self):
        assert self.uow.analytics.aggregate_daily_calls == [self.yesterday]


class Scenario2(vedro.Scenario):
    subject = "daily aggregation handles already-existing stats gracefully"

    def given_analytics_processor_where_daily_stats_already_exist(self):
        self.uow = FakeUnitOfWork()
        self.uow.analytics.aggregate_daily_result = None

        self.processor = AnalyticsJobProcessor(
            database=_STUB,
            settings=_STUB,
            uow_factory=lambda *a, **kw: self.uow,
        )

    async def when_aggregate_daily_stats_is_called(self):
        self.raised = False
        try:
            await self.processor._aggregate_daily_stats()
        except Exception:
            self.raised = True

    def then_no_exception_is_raised(self):
        assert self.raised is False

    def and_aggregate_daily_was_still_called(self):
        assert len(self.uow.analytics.aggregate_daily_calls) == 1
