"""Test scenario for adding duplicate MR (idempotency check)."""

import vedro

from gitlab_queue.core.queue import QueueManager
from scenarios.contexts.sqlite_client import initialized_test_database

from ._helpers import create_test_mr


class Scenario(vedro.Scenario):
    subject = "add duplicate mr is idempotent"

    async def given_queue_with_existing_mr(self):
        self._db_context = initialized_test_database()
        self.db = await self._db_context.__aenter__()
        self.queue = QueueManager(db=self.db)
        await self.queue.ensure_schema()
        # Add MR first time
        mr = create_test_mr(iid=42, title="Original Title")
        self.first_item = await self.queue.add_to_queue(mr)

    async def when_same_mr_is_added_again(self):
        # Try to add same MR with different title
        mr = create_test_mr(iid=42, title="New Title")
        self.second_item = await self.queue.add_to_queue(mr)

    def then_returned_item_should_be_the_existing_one(self):
        assert self.second_item.mr_iid == self.first_item.mr_iid
        # Title should be original (not updated)
        assert self.second_item.title == "Original Title"

    async def and_queue_should_still_have_one_item(self):
        """
        Assert that the queue contains exactly one item.
        """
        length = await self.queue.get_queue_length()
        assert length == 1

    async def and_position_should_still_be_1(self):
        """
        Verifies that the queue position for merge request IID 42 remains 1.

        Checks the stored position for MR with IID 42 and asserts it equals 1.
        """
        position = await self.queue.get_queue_position(42)
        assert position == 1

    async def do_cleanup(self):
        """
        Close the test database context and release associated resources.

        This method awaits the async context manager's exit to ensure the test database is properly closed.
        """
        await self._db_context.__aexit__(None, None, None)
