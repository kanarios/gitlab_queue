"""Test that get_next_queued returns None when no queued MRs exist."""

from __future__ import annotations

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database
from scenarios.integration.repositories._helpers import create_tables

from gitlab_queue.db.repositories import MergeRequestRepository


class Scenario(vedro.Scenario):
    subject = "get_next_queued returns none when queue is empty"

    async def given_empty_database(self):
        self._db_ctx = initialized_test_database()
        self.db = await self._db_ctx.__aenter__()
        await create_tables(self.db)

    async def when_get_next_queued_is_called(self):
        async with self.db.session() as session:
            repo = MergeRequestRepository(session)
            self.result = await repo.get_next_queued()

    def then_result_should_be_none(self):
        assert self.result is None

    async def do_cleanup(self):
        await self._db_ctx.__aexit__(None, None, None)
