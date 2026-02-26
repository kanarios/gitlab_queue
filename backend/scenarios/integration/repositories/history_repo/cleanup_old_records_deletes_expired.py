"""Test that cleanup_old_records deletes expired history records."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database
from scenarios.integration.repositories._helpers import create_tables, seed_history

from gitlab_queue.db.repositories import HistoryRepository


class Scenario(vedro.Scenario):
    subject = "cleanup_old_records deletes expired history records"

    async def given_database_with_old_and_recent_history(self):
        """
        Prepare a test database containing one expired and one recent history record.

        Initializes an async test database context, creates required tables, and seeds two history entries:
        - iid=1 with finished_at set to 400 days before now (expired)
        - iid=2 with finished_at set to now (recent)

        Side effects:
        - stores the async database context on self._db_ctx and the opened database on self.db for use by subsequent steps.
        """
        self._db_ctx = initialized_test_database()
        self.db = await self._db_ctx.__aenter__()
        await create_tables(self.db)

        now = datetime.now(UTC)
        async with self.db.transaction() as session:
            await seed_history(
                session,
                iid=1,
                finished_at=(now - timedelta(days=400)).isoformat(),
            )
            await seed_history(
                session,
                iid=2,
                finished_at=now.isoformat(),
            )

    async def when_cleanup_old_records_is_called(self):
        """
        Executes the repository cleanup with a 1-day retention and records the number of deleted history records.

        This method runs the cleanup operation against the test database and stores the resulting deleted count in self.deleted_count.
        """
        async with self.db.transaction() as session:
            repo = HistoryRepository(session)
            self.deleted_count = await repo.cleanup_old_records(retention_days=1)

    def then_one_record_should_be_deleted(self):
        assert self.deleted_count == 1

    async def and_recent_record_should_remain(self):
        """
        Assert that only the recent history record remains in the database.

        Fetches history from the repository and asserts that exactly one record is present and its `iid` equals 2.
        """
        async with self.db.session() as session:
            repo = HistoryRepository(session)
            result = await repo.get_history()
            assert result.total == 1
            assert result.items[0].iid == 2

    async def do_cleanup(self):
        """
        Tears down the initialized test database context used by the scenario.
        """
        await self._db_ctx.__aexit__(None, None, None)
