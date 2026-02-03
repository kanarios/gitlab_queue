"""Test that get_recent returns limited number of entries."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database
from scenarios.integration.repositories._helpers import create_tables, seed_history

from gitlab_queue.db.repositories import HistoryRepository


class Scenario(vedro.Scenario):
    subject = "get_recent returns limited number of entries"

    async def given_database_with_history_records(self):
        self._db_ctx = initialized_test_database()
        self.db = await self._db_ctx.__aenter__()
        await create_tables(self.db)

        now = datetime.now(UTC)
        async with self.db.transaction() as session:
            for i in range(5):
                await seed_history(
                    session,
                    iid=100 + i,
                    finished_at=(now - timedelta(minutes=i)).isoformat(),
                )

    async def when_get_recent_is_called_with_limit(self):
        async with self.db.session() as session:
            repo = HistoryRepository(session)
            self.result = await repo.get_recent(limit=3)

    def then_only_3_records_should_be_returned(self):
        assert len(self.result) == 3

    async def do_cleanup(self):
        await self._db_ctx.__aexit__(None, None, None)
