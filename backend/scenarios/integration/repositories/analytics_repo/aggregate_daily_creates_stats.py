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
        """
        Prepare a test database populated with predefined history and hourly records for aggregate_daily testing.

        Creates and opens an initialized test database, creates required tables, fixes the target date to 2026-01-15, and inserts two history records (IID 1: merged and marked hotfix; IID 2: failed) plus a single hourly record with queue_depth 10 to be used by the aggregate_daily test.
        """
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
                is_hotfix=True,
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
        """
        Execute the daily aggregation for the scenario's target date and store the resulting daily statistics on self.daily.

        After completion, self.daily will contain the created or updated daily record for the target date.
        """
        async with self.db.transaction() as session:
            repo = AnalyticsRepository(session)
            self.daily = await repo.aggregate_daily(self.target_date)

    def then_daily_record_should_be_created(self):
        """
        Assert that a daily statistics record was created with expected counts and queue depth.

        Asserts that self.daily is present and has total_processed == 2, success_count == 1, failed_count == 1, hotfix_count == 1, and max_queue_depth == 10.
        """
        assert self.daily is not None
        assert self.daily.total_processed == 2
        assert self.daily.success_count == 1
        assert self.daily.failed_count == 1
        assert self.daily.hotfix_count == 1
        assert self.daily.max_queue_depth == 10

    async def do_cleanup(self):
        """
        Close and clean up the test database context, releasing its associated resources.

        Ensures the database context manager created during setup is exited so connections and temporary state are released.
        """
        await self._db_ctx.__aexit__(None, None, None)
