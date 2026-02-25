"""Test scenario: remove existing MR from queue."""

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database

from gitlab_queue.core.queue import QueueManager

from ._helpers import create_test_mr


class Scenario(vedro.Scenario):
    subject = "remove existing MR from queue"

    async def given_queue_with_mr(self):
        self._db_context = initialized_test_database()
        self.db = await self._db_context.__aenter__()
        self.queue = QueueManager(db=self.db)
        await self.queue.ensure_schema()
        mr = create_test_mr(iid=42)
        await self.queue.add_to_queue(mr)

    async def when_mr_is_removed(self):
        self.result = await self.queue.remove_from_queue(42)

    def then_result_should_be_true(self):
        assert self.result is True

    async def and_mr_state_should_be_removed(self):
        state = await self.queue.get_mr_state(42)
        assert state is not None
        assert state["status"] == "removed"

    async def and_queue_should_be_empty(self):
        length = await self.queue.get_queue_length()
        assert length == 0

    async def do_cleanup(self):
        await self._db_context.__aexit__(None, None, None)
