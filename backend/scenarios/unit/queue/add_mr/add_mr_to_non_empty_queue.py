"""Test scenario for adding MR to non-empty queue."""

import vedro

from gitlab_queue.core.queue import QueueManager
from scenarios.contexts.sqlite_client import initialized_test_database

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
        await self.queue.add_to_queue(99999, first_mr)

    async def when_second_mr_is_added(self):
        second_mr = create_test_mr(iid=2, title="Second MR")
        self.item = await self.queue.add_to_queue(99999, second_mr)

    async def then_item_should_be_at_position_2(self):
        """
        Verify that the merge request with iid 2 is at queue position 2.

        Raises:
                AssertionError: If the queue position for iid 2 is not equal to 2.
        """
        position = await self.queue.get_queue_position(99999, 2)
        assert position == 2

    async def and_first_mr_should_still_be_at_position_1(self):
        """
        Asserts that the merge request with IID 1 remains at queue position 1.

        Raises:
            AssertionError: If the MR's queue position is not 1.
        """
        position = await self.queue.get_queue_position(99999, 1)
        assert position == 1

    async def and_queue_length_should_be_2(self):
        """
        Assert that the queue contains exactly two items.

        Raises:
            AssertionError: if the queue length is not 2.
        """
        length = await self.queue.get_queue_length()
        assert length == 2

    async def do_cleanup(self):
        """
        Release the test database context and clean up associated resources.

        Exits the asynchronous database context manager obtained during scenario setup to close connections and perform teardown.
        """
        await self._db_context.__aexit__(None, None, None)
