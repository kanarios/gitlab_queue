"""Test that get_by_iid returns None when MR does not exist."""

from __future__ import annotations

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database
from scenarios.integration.repositories._helpers import create_tables

from gitlab_queue.db.repositories import MergeRequestRepository


class Scenario(vedro.Scenario):
    subject = "get_by_iid returns none when mr not found"

    async def given_empty_database(self):
        self._db_ctx = initialized_test_database()
        self.db = await self._db_ctx.__aenter__()
        await create_tables(self.db)

    async def when_get_by_iid_is_called_for_nonexistent_mr(self):
        async with self.db.session() as session:
            repo = MergeRequestRepository(session)
            self.result = await repo.get_by_iid(999)

    def then_result_should_be_none(self):
        assert self.result is None

    async def do_cleanup(self):
        if hasattr(self, "_db_ctx"):
            await self._db_ctx.__aexit__(None, None, None)
