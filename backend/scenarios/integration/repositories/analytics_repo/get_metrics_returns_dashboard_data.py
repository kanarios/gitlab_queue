"""Test that get_metrics returns dashboard data."""

from __future__ import annotations

from datetime import UTC, datetime

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database
from scenarios.integration.repositories._helpers import (
    create_tables,
    seed_history,
    seed_hourly,
    seed_mr,
)

from gitlab_queue.db.repositories import AnalyticsRepository


class Scenario(vedro.Scenario):
    subject = "get_metrics returns dashboard data"

    async def given_database_with_some_data(self):
        self._db_ctx = initialized_test_database()
        self.db = await self._db_ctx.__aenter__()
        await create_tables(self.db)

        now = datetime.now(UTC)
        today_ts = now.replace(minute=0, second=0, microsecond=0).isoformat()

        async with self.db.transaction() as session:
            await seed_mr(session, iid=1, status="queued")
            await seed_mr(session, iid=2, status="rebasing")

            await seed_history(
                session,
                iid=10,
                status="merged",
                wait_time_seconds=60,
                processing_time_seconds=120,
                finished_at=now.isoformat(),
            )
            await seed_history(
                session,
                iid=11,
                status="failed",
                wait_time_seconds=30,
                processing_time_seconds=90,
                finished_at=now.isoformat(),
            )

            await seed_hourly(
                session,
                timestamp=today_ts,
                queue_depth=5,
                processed_count=3,
            )

    async def when_get_metrics_is_called(self):
        async with self.db.session() as session:
            repo = AnalyticsRepository(session)
            self.metrics = await repo.get_metrics(7)

    def then_metrics_should_contain_queue_count(self):
        assert self.metrics.total_in_queue == 2

    def and_metrics_should_contain_merged_count(self):
        assert self.metrics.merged_count == 1

    def and_metrics_should_contain_failed_count(self):
        assert self.metrics.failed_count == 1

    def and_success_rate_should_be_calculated(self):
        assert self.metrics.success_rate == 50.0

    def and_hourly_trend_should_have_data(self):
        assert len(self.metrics.hourly_trend) >= 1

    async def do_cleanup(self):
        if hasattr(self, "_db_ctx"):
            await self._db_ctx.__aexit__(None, None, None)
