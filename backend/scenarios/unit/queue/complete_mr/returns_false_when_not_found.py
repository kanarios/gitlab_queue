"""Test scenario: complete_mr returns False when MR not found."""

from __future__ import annotations

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database

from gitlab_queue.core.queue import QueueManager


class Scenario(vedro.Scenario):
    subject = "complete mr returns false when mr not found"

    async def given_empty_queue(self):
        self._db_context = initialized_test_database()
        self.db = await self._db_context.__aenter__()
        self.queue = QueueManager(db=self.db)
        await self.queue.ensure_schema()

    async def when_completing_nonexistent_mr(self):
        self.result = await self.queue.complete_mr(999, "merged")

    def then_result_should_be_false(self):
        assert self.result is False

    async def do_cleanup(self):
        await self._db_context.__aexit__(None, None, None)
