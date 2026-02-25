"""Test scenario: get_mr_state returns None for unknown MR."""

from __future__ import annotations

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database

from gitlab_queue.core.queue import QueueManager


class Scenario(vedro.Scenario):
    subject = "get mr state returns none when not found"

    async def given_empty_queue(self):
        self._db_context = initialized_test_database()
        self.db = await self._db_context.__aenter__()
        self.queue = QueueManager(db=self.db)
        await self.queue.ensure_schema()

    async def when_state_is_retrieved_for_unknown_mr(self):
        self.state = await self.queue.get_mr_state(999)

    def then_state_should_be_none(self):
        assert self.state is None

    async def do_cleanup(self):
        await self._db_context.__aexit__(None, None, None)
