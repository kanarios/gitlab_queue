"""Test that cleanup removes data older than retention period.

Covers _cleanup_hourly_analytics:
- Calls analytics.cleanup_hourly(retention_days)
- Runs VACUUM when records are deleted
- No VACUUM when nothing to clean up

Also covers _cleanup_history for 1-year retention.
"""

from __future__ import annotations

import vedro

from gitlab_queue.jobs.analytics import AnalyticsJobProcessor
from scenarios.fakes import FakeUnitOfWork

_STUB = object()


def _create_vacuum_tracker():
    calls: list[None] = []

    async def fake_vacuum() -> None:
        calls.append(None)

    return fake_vacuum, calls


class Scenario(vedro.Scenario):
    subject = "cleanup removes hourly analytics older than 30 days and runs vacuum"

    def given_analytics_processor_with_old_data(self):
        self.uow = FakeUnitOfWork()
        self.uow.analytics.cleanup_hourly_result = 150

        fake_vacuum, self.vacuum_calls = _create_vacuum_tracker()
        self.processor = AnalyticsJobProcessor(
            database=_STUB,
            settings=_STUB,
            uow_factory=lambda *a, **kw: self.uow,
            vacuum_fn=fake_vacuum,
        )

    async def when_cleanup_hourly_analytics_is_called(self):
        await self.processor._cleanup_hourly_analytics()

    def then_cleanup_was_called_with_30_day_retention(self):
        assert self.uow.analytics.cleanup_hourly_calls == [30]

    def and_vacuum_was_triggered(self):
        assert len(self.vacuum_calls) == 1


class Scenario2(vedro.Scenario):
    subject = "cleanup skips vacuum when no records are deleted"

    def given_analytics_processor_with_no_old_data(self):
        self.uow = FakeUnitOfWork()
        self.uow.analytics.cleanup_hourly_result = 0

        fake_vacuum, self.vacuum_calls = _create_vacuum_tracker()
        self.processor = AnalyticsJobProcessor(
            database=_STUB,
            settings=_STUB,
            uow_factory=lambda *a, **kw: self.uow,
            vacuum_fn=fake_vacuum,
        )

    async def when_cleanup_hourly_analytics_is_called(self):
        await self.processor._cleanup_hourly_analytics()

    def then_cleanup_was_called(self):
        assert self.uow.analytics.cleanup_hourly_calls == [30]

    def and_vacuum_was_not_triggered(self):
        assert self.vacuum_calls == []


class Scenario3(vedro.Scenario):
    subject = "history cleanup removes records older than 365 days"

    def given_analytics_processor_with_old_history(self):
        self.uow = FakeUnitOfWork()
        self.uow.history.cleanup_old_records_result = 50

        fake_vacuum, self.vacuum_calls = _create_vacuum_tracker()
        self.processor = AnalyticsJobProcessor(
            database=_STUB,
            settings=_STUB,
            uow_factory=lambda *a, **kw: self.uow,
            vacuum_fn=fake_vacuum,
        )

    async def when_cleanup_history_is_called(self):
        await self.processor._cleanup_history()

    def then_cleanup_was_called_with_365_day_retention(self):
        assert self.uow.history.cleanup_old_records_calls == [365]

    def and_vacuum_was_triggered(self):
        assert len(self.vacuum_calls) == 1
