"""Test that aggregate_daily skips if daily record already exists."""

from __future__ import annotations

from datetime import date

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database
from scenarios.integration.repositories._helpers import create_tables

from gitlab_queue.db.models import AnalyticsDailyModel
from gitlab_queue.db.repositories import AnalyticsRepository


class Scenario(vedro.Scenario):
    subject = "aggregate_daily skips if daily record already exists"

    async def given_database_with_existing_daily_record(self):
        self._db_ctx = initialized_test_database()
        self.db = await self._db_ctx.__aenter__()
        await create_tables(self.db)

        self.target_date = date.today()

        async with self.db.transaction() as session:
            daily = AnalyticsDailyModel(
                date=self.target_date.isoformat(),
                total_processed=5,
                success_count=4,
                failed_count=1,
                conflict_count=0,
                timeout_count=0,
                hotfix_count=0,
                avg_wait_time_seconds=30,
                avg_processing_time_seconds=60,
                max_queue_depth=3,
            )
            session.add(daily)
            await session.flush()

    async def when_aggregate_daily_is_called_again(self):
        async with self.db.transaction() as session:
            repo = AnalyticsRepository(session)
            self.result = await repo.aggregate_daily(self.target_date)

    def then_result_should_be_none(self):
        assert self.result is None

    async def do_cleanup(self):
        if hasattr(self, "_db_ctx"):
            await self._db_ctx.__aexit__(None, None, None)
