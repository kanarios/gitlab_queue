"""Test scenario: remove non-existent MR."""

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database

from gitlab_queue.core.queue import QueueManager


class Scenario(vedro.Scenario):
    subject = "remove non-existent MR"

    async def given_empty_queue(self):
        self._db_context = initialized_test_database()
        self.db = await self._db_context.__aenter__()
        self.queue = QueueManager(db=self.db)
        await self.queue.ensure_schema()

    async def when_nonexistent_mr_is_removed(self):
        self.result = await self.queue.remove_from_queue(999)

    def then_result_should_be_false(self):
        assert self.result is False, f"Expected False, got {self.result}"

    async def and_queue_should_still_be_empty(self):
        length = await self.queue.get_queue_length()
        assert length == 0, f"Expected 0, got {length}"

    async def do_cleanup(self):
        if hasattr(self, "_db_context"):
            await self._db_context.__aexit__(None, None, None)
