"""Test that get_stats_for_last_hour returns only recent statistics."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database
from scenarios.integration.repositories._helpers import create_tables, seed_history

from gitlab_queue.db.repositories import HistoryRepository


class Scenario(vedro.Scenario):
    subject = "get_stats_for_last_hour returns only recent statistics"

    async def given_database_with_recent_and_old_history(self):
        """
        Set up a test database and seed it with one recent and one old history record.
        
        Creates tables in a temporary test database, opens a transactional session, and inserts two history entries:
        - iid=1, status="merged", finished_at = now (UTC) minus 30 minutes (recent)
        - iid=2, status="merged", finished_at = now (UTC) minus 3 hours (old)
        """
        self._db_ctx = initialized_test_database()
        self.db = await self._db_ctx.__aenter__()
        await create_tables(self.db)

        now = datetime.now(UTC)
        async with self.db.transaction() as session:
            await seed_history(
                session,
                iid=1,
                status="merged",
                finished_at=(now - timedelta(minutes=30)).isoformat(),
            )
            await seed_history(
                session,
                iid=2,
                status="merged",
                finished_at=(now - timedelta(hours=3)).isoformat(),
            )

    async def when_get_stats_for_last_hour_is_called(self):
        """
        Retrieve statistics for the previous hour and store the result on self.stats.
        """
        async with self.db.session() as session:
            repo = HistoryRepository(session)
            self.stats = await repo.get_stats_for_last_hour()

    def then_only_recent_record_should_be_counted(self):
        """
        Asserts that the repository statistics count only the recent history record.
        
        Raises:
        	AssertionError: If `self.stats.total_processed` is not 1 or `self.stats.success_count` is not 1.
        """
        assert self.stats.total_processed == 1
        assert self.stats.success_count == 1

    async def do_cleanup(self):
        """
        Tear down the test database context used by the scenario.
        
        Exits the asynchronous database context manager to release connections and other resources.
        """
        await self._db_ctx.__aexit__(None, None, None)
