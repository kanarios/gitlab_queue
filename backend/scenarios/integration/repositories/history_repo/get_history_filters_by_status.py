"""Test that get_history filters by status."""

from __future__ import annotations

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database
from scenarios.integration.repositories._helpers import create_tables, seed_history

from gitlab_queue.db.repositories import HistoryRepository


class Scenario(vedro.Scenario):
    subject = "get_history filters by status"

    async def given_database_with_mixed_status_history(self):
        self._db_ctx = initialized_test_database()
        self.db = await self._db_ctx.__aenter__()
        await create_tables(self.db)

        async with self.db.transaction() as session:
            await seed_history(session, iid=1, status="merged")
            await seed_history(session, iid=2, status="merged")
            await seed_history(session, iid=3, status="failed")
            await seed_history(session, iid=4, status="conflict")

    async def when_get_history_is_called_with_status_filter(self):
        self._session_ctx = self.db.session()
        session = await self._session_ctx.__aenter__()
        repo = HistoryRepository(session)
        self.result = await repo.get_history(status_filter="merged")

    def then_only_merged_records_should_be_returned(self):
        assert self.result.total == 2
        for item in self.result.items:
            assert item.status == "merged"

    async def do_cleanup(self):
        if hasattr(self, "_session_ctx"):
            await self._session_ctx.__aexit__(None, None, None)
        if hasattr(self, "_db_ctx"):
            await self._db_ctx.__aexit__(None, None, None)
