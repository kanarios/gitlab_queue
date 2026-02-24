"""Test that aggregate_daily creates daily statistics."""

from __future__ import annotations

from datetime import UTC, date, datetime

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database
from scenarios.integration.repositories._helpers import (
    create_tables,
    seed_history,
    seed_hourly,
)

from gitlab_queue.db.repositories import AnalyticsRepository


class Scenario(vedro.Scenario):
    subject = "aggregate_daily creates daily statistics from history and hourly data"

    async def given_database_with_history_and_hourly_data(self):
        self._db_ctx = initialized_test_database()
        self.db = await self._db_ctx.__aenter__()
        await create_tables(self.db)

        # Use a fixed date to avoid timezone boundary issues
        self.target_date = date(2026, 1, 15)
        now = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)
        today_ts = now.replace(minute=0, second=0, microsecond=0).isoformat()

        async with self.db.transaction() as session:
            await seed_history(
                session,
                iid=1,
                status="merged",
                is_hotfix=1,
                wait_time_seconds=60,
                processing_time_seconds=120,
                finished_at=now.isoformat(),
            )
            await seed_history(
                session,
                iid=2,
                status="failed",
                wait_time_seconds=30,
                processing_time_seconds=90,
                finished_at=now.isoformat(),
            )
            await seed_hourly(
                session,
                timestamp=today_ts,
                queue_depth=10,
            )

    async def when_aggregate_daily_is_called(self):
        async with self.db.transaction() as session:
            repo = AnalyticsRepository(session)
            self.daily = await repo.aggregate_daily(self.target_date)

    def then_daily_record_should_be_created(self):
        assert self.daily is not None
        assert self.daily.total_processed == 2
        assert self.daily.success_count == 1
        assert self.daily.failed_count == 1
        assert self.daily.hotfix_count == 1
        assert self.daily.max_queue_depth == 10

    async def do_cleanup(self):
        if hasattr(self, "_db_ctx"):
            await self._db_ctx.__aexit__(None, None, None)
