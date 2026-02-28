"""Test that cleanup_hourly deletes old hourly records."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database
from scenarios.integration.repositories._helpers import (
    create_tables,
    seed_hourly,
)

from gitlab_queue.db.repositories import AnalyticsRepository


class Scenario(vedro.Scenario):
    subject = "cleanup_hourly deletes old hourly records"

    async def given_database_with_old_and_recent_hourly(self):
        """
        Prepare a test database and seed it with one old hourly record and one recent hourly record.

        Creates an initialized test database, ensures tables exist, and inserts two hourly entries:
        one timestamped 60 days ago (rounded to the hour) with queue_depth 3, and one for the current hour
        (rounded to the hour) with queue_depth 7. Intended as setup for tests that verify cleanup behavior.
        """
        self._db_ctx = initialized_test_database()
        self.db = await self._db_ctx.__aenter__()
        await create_tables(self.db)

        now = datetime.now(UTC)
        old_ts = (
            (now - timedelta(days=60))
            .replace(
                minute=0,
                second=0,
                microsecond=0,
            )
            .isoformat()
        )
        recent_ts = now.replace(minute=0, second=0, microsecond=0).isoformat()

        async with self.db.transaction() as session:
            await seed_hourly(session, timestamp=old_ts, queue_depth=3)
            await seed_hourly(session, timestamp=recent_ts, queue_depth=7)

    async def when_cleanup_hourly_is_called(self):
        """
        Calls AnalyticsRepository.cleanup_hourly with retention_days=1 and stores the number of deleted hourly records in self.deleted_count.

        This step runs the cleanup inside a database transaction.
        """
        async with self.db.transaction() as session:
            repo = AnalyticsRepository(session)
            self.deleted_count = await repo.cleanup_hourly(retention_days=1)

    def then_one_record_should_be_deleted(self):
        assert self.deleted_count == 1

    async def and_recent_record_should_remain(self):
        """
        Verify the recent hourly metric with queue_depth 7 is preserved and exactly one hourly entry exists.

        Fetch metrics for queue_depth 7 and assert that there is exactly one entry in metrics.hourly_trend and that its "queue_depth" equals 7.
        """
        async with self.db.session() as session:
            repo = AnalyticsRepository(session)
            metrics = await repo.get_metrics(7)
            assert len(metrics.hourly_trend) == 1
            assert metrics.hourly_trend[0]["queue_depth"] == 7

    async def do_cleanup(self):
        """
        Close the test database context.

        Exit the internal context manager to release database resources and complete teardown.
        """
        await self._db_ctx.__aexit__(None, None, None)
