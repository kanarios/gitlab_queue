"""Test that add creates a new record in the database."""

from __future__ import annotations

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database
from scenarios.integration.repositories._helpers import (
    create_tables,
    create_test_mr_model,
)

from gitlab_queue.db.repositories import MergeRequestRepository


class Scenario(vedro.Scenario):
    subject = "add creates a new merge request record"

    async def given_empty_database(self):
        self._db_ctx = initialized_test_database()
        self.db = await self._db_ctx.__aenter__()
        await create_tables(self.db)

    async def when_mr_is_added(self):
        async with self.db.transaction() as session:
            repo = MergeRequestRepository(session)
            mr = create_test_mr_model(iid=42, title="New MR")
            self.added_mr = await repo.add(mr)

    def then_added_mr_should_have_an_id(self):
        assert self.added_mr.id is not None

    async def and_mr_should_be_in_database(self):
        async with self.db.session() as session:
            repo = MergeRequestRepository(session)
            result = await repo.get_by_iid(42)
            assert result is not None
            assert result.title == "New MR"

    async def do_cleanup(self):
        if hasattr(self, "_db_ctx"):
            await self._db_ctx.__aexit__(None, None, None)
