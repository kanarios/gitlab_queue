"""Test that save_hourly_snapshot creates a record."""

from __future__ import annotations

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database
from scenarios.integration.repositories._helpers import create_tables

from gitlab_queue.db.repositories import AnalyticsRepository


class Scenario(vedro.Scenario):
    subject = "save_hourly_snapshot creates analytics record"

    async def given_empty_database(self):
        self._db_ctx = initialized_test_database()
        self.db = await self._db_ctx.__aenter__()
        await create_tables(self.db)

    async def when_save_hourly_snapshot_is_called(self):
        async with self.db.transaction() as session:
            repo = AnalyticsRepository(session)
            self.snapshot = await repo.save_hourly_snapshot(
                queue_depth=5,
                processed_count=3,
                success_count=2,
                failed_count=1,
                avg_wait_time_seconds=60,
            )

    def then_snapshot_should_be_created(self):
        assert self.snapshot is not None
        assert self.snapshot.id is not None
        assert self.snapshot.queue_depth == 5
        assert self.snapshot.processed_count == 3
        assert self.snapshot.success_count == 2
        assert self.snapshot.failed_count == 1
        assert self.snapshot.avg_wait_time_seconds == 60

    def and_timestamp_should_be_truncated_to_hour(self):
        from datetime import datetime

        ts = datetime.fromisoformat(self.snapshot.timestamp)
        assert ts.minute == 0
        assert ts.second == 0
        assert ts.microsecond == 0

    async def do_cleanup(self):
        await self._db_ctx.__aexit__(None, None, None)
