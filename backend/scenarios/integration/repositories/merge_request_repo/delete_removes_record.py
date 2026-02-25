"""Test that delete removes an MR record from the database."""

from __future__ import annotations

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database
from scenarios.integration.repositories._helpers import create_tables, seed_mr

from gitlab_queue.db.repositories import MergeRequestRepository


class Scenario(vedro.Scenario):
    subject = "delete removes merge request record"

    async def given_database_with_mr(self):
        self._db_ctx = initialized_test_database()
        self.db = await self._db_ctx.__aenter__()
        await create_tables(self.db)

        async with self.db.transaction() as session:
            await seed_mr(session, iid=42)

    async def when_mr_is_deleted(self):
        async with self.db.transaction() as session:
            repo = MergeRequestRepository(session)
            self.deleted = await repo.delete(42)

    def then_delete_should_succeed(self):
        assert self.deleted is True

    async def and_mr_should_not_be_in_database(self):
        async with self.db.session() as session:
            repo = MergeRequestRepository(session)
            result = await repo.get_by_iid(42)
            assert result is None

    async def do_cleanup(self):
        await self._db_ctx.__aexit__(None, None, None)
