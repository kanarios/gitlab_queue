"""Test that get_position returns None for a non-existent MR."""

from __future__ import annotations

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database
from scenarios.integration.repositories._helpers import create_tables

from gitlab_queue.db.repositories import MergeRequestRepository


class Scenario(vedro.Scenario):
    subject = "get_position returns none for missing merge request"

    async def given_empty_database(self):
        self._db_ctx = initialized_test_database()
        self.db = await self._db_ctx.__aenter__()
        await create_tables(self.db)

    async def when_get_position_is_called_for_nonexistent_mr(self):
        async with self.db.session() as session:
            repo = MergeRequestRepository(session)
            self.position = await repo.get_position(999)

    def then_position_should_be_none(self):
        assert self.position is None

    async def do_cleanup(self):
        if hasattr(self, "_db_ctx"):
            await self._db_ctx.__aexit__(None, None, None)
