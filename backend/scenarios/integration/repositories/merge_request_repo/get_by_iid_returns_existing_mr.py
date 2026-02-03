"""Test that get_by_iid returns an existing MR."""

from __future__ import annotations

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database
from scenarios.integration.repositories._helpers import create_tables, seed_mr

from gitlab_queue.db.repositories import MergeRequestRepository


class Scenario(vedro.Scenario):
    subject = "get_by_iid returns existing merge request"

    async def given_database_with_mr(self):
        self._db_ctx = initialized_test_database()
        self.db = await self._db_ctx.__aenter__()
        await create_tables(self.db)

        async with self.db.transaction() as session:
            await seed_mr(session, iid=42, title="Test MR")

    async def when_get_by_iid_is_called(self):
        self._session_ctx = self.db.session()
        session = await self._session_ctx.__aenter__()
        repo = MergeRequestRepository(session)
        self.result = await repo.get_by_iid(42)

    def then_result_should_be_the_mr(self):
        assert self.result is not None
        assert self.result.iid == 42
        assert self.result.title == "Test MR"

    async def do_cleanup(self):
        await self._session_ctx.__aexit__(None, None, None)
        await self._db_ctx.__aexit__(None, None, None)
