"""Test that hourly snapshot records current queue state.

Covers _save_hourly_snapshot:
- Gets current queue depth from merge_requests.count_active()
- Gets stats from history.get_stats_for_last_hour()
- Saves snapshot via analytics.save_hourly_snapshot()
"""

from __future__ import annotations

import vedro

from gitlab_queue.jobs.analytics import AnalyticsJobProcessor
from scenarios.fakes import FakeUnitOfWork, HourlyStats

_STUB = object()


class Scenario(vedro.Scenario):
    subject = "hourly snapshot records current queue state"

    def given_analytics_processor_with_queue_data(self):
        self.uow = FakeUnitOfWork()
        self.uow.merge_requests.active_count = 5
        self.uow.history.hourly_stats = HourlyStats(
            total_processed=10,
            success_count=8,
            failed_count=2,
            avg_wait_time_seconds=120.6,
        )

        self.processor = AnalyticsJobProcessor(
            database=_STUB,
            settings=_STUB,
            uow_factory=lambda *a, **kw: self.uow,
        )

    async def when_save_hourly_snapshot_is_called(self):
        await self.processor._save_hourly_snapshot()

    def then_queue_depth_was_fetched(self):
        assert len(self.uow.merge_requests.count_active_calls) == 1

    def and_hourly_stats_were_fetched(self):
        assert len(self.uow.history.get_stats_calls) == 1

    def and_snapshot_was_saved_with_correct_data(self):
        assert self.uow.analytics.save_hourly_snapshot_calls == [
            {
                "queue_depth": 5,
                "processed_count": 10,
                "success_count": 8,
                "failed_count": 2,
                "avg_wait_time_seconds": 120,
            }
        ]
