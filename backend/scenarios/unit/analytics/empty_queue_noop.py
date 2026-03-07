"""Test that analytics operations are no-op when queue is empty.

Covers _save_hourly_snapshot with zero queue depth and zero stats,
and verifies that exceptions in the snapshot job are caught.
"""

from __future__ import annotations

import vedro

from gitlab_queue.jobs.analytics import AnalyticsJobProcessor
from scenarios.fakes import FakeUnitOfWork

_STUB = object()


class Scenario(vedro.Scenario):
    subject = "hourly snapshot saves zero counts when queue is empty"

    def given_analytics_processor_with_empty_queue(self):
        self.uow = FakeUnitOfWork()

        self.processor = AnalyticsJobProcessor(
            database=_STUB,
            settings=_STUB,
            uow_factory=lambda *a, **kw: self.uow,
        )

    async def when_save_hourly_snapshot_is_called(self):
        await self.processor._save_hourly_snapshot()

    def then_snapshot_was_saved_with_zero_values(self):
        assert self.uow.analytics.save_hourly_snapshot_calls == [
            {
                "queue_depth": 0,
                "processed_count": 0,
                "success_count": 0,
                "failed_count": 0,
                "avg_wait_time_seconds": None,
            }
        ]


class Scenario2(vedro.Scenario):
    subject = "hourly snapshot catches exception and does not propagate"

    def given_analytics_processor_where_database_raises(self):
        self.uow = FakeUnitOfWork(
            enter_error=RuntimeError("Database connection lost"),
        )

        self.processor = AnalyticsJobProcessor(
            database=_STUB,
            settings=_STUB,
            uow_factory=lambda *a, **kw: self.uow,
        )

    async def when_save_hourly_snapshot_is_called(self):
        await self.processor._save_hourly_snapshot()

    def then_snapshot_was_not_called(self):
        assert self.uow.analytics.save_hourly_snapshot_calls == []
