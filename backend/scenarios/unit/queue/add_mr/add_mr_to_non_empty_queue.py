"""Test scenario for adding MR to non-empty queue."""

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database

from gitlab_queue.core.queue import QueueManager

from ._helpers import create_test_mr


class Scenario(vedro.Scenario):
    subject = "add mr to non-empty queue"

    async def given_queue_with_one_mr(self):
        self._db_context = initialized_test_database()
        self.db = await self._db_context.__aenter__()
        self.queue = QueueManager(db=self.db)
        await self.queue.ensure_schema()
        # Add first MR
        first_mr = create_test_mr(iid=1, title="First MR")
        await self.queue.add_to_queue(first_mr)

    async def when_second_mr_is_added(self):
        second_mr = create_test_mr(iid=2, title="Second MR")
        self.item = await self.queue.add_to_queue(second_mr)

    async def then_item_should_be_at_position_2(self):
        position = await self.queue.get_queue_position(2)
        assert position == 2, f"Expected position 2, got {position}"

    async def and_first_mr_should_still_be_at_position_1(self):
        position = await self.queue.get_queue_position(1)
        assert position == 1, f"Expected position 1, got {position}"

    async def and_queue_length_should_be_2(self):
        length = await self.queue.get_queue_length()
        assert length == 2, f"Expected length 2, got {length}"

    async def do_cleanup(self):
        if hasattr(self, "_db_context"):
            await self._db_context.__aexit__(None, None, None)
