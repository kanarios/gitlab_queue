"""Test that update rejects disallowed fields."""

from __future__ import annotations

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database
from scenarios.integration.repositories._helpers import create_tables, seed_mr

from gitlab_queue.db.repositories import MergeRequestRepository


class Scenario(vedro.Scenario):
    subject = "update rejects disallowed fields like title"

    async def given_database_with_mr(self):
        self._db_ctx = initialized_test_database()
        self.db = await self._db_ctx.__aenter__()
        await create_tables(self.db)

        async with self.db.transaction() as session:
            await seed_mr(session, iid=42, title="Original Title")

    async def when_update_is_called_with_disallowed_field(self):
        async with self.db.transaction() as session:
            repo = MergeRequestRepository(session)
            self.updated = await repo.update(42, title="New Title")

    def then_update_should_return_true(self):
        assert self.updated is True

    async def and_title_should_remain_unchanged(self):
        async with self.db.session() as session:
            repo = MergeRequestRepository(session)
            mr = await repo.get_by_iid(42)
            assert mr is not None
            assert mr.title == "Original Title", f"Title should not change, got '{mr.title}'"

    async def do_cleanup(self):
        await self._db_ctx.__aexit__(None, None, None)
