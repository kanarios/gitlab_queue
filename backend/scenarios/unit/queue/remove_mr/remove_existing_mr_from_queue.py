"""Test scenario: remove existing MR from queue."""

import vedro

from gitlab_queue.core.queue import QueueManager
from scenarios.contexts.sqlite_client import initialized_test_database

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
        """
        Attempt to remove the merge request with IID 42 from the queue and
        store the result.
        """
        self.result = await self.queue.remove_from_queue(42)

    def then_result_should_be_true(self):
        """
        Verify that the MR removal operation succeeded.

        Raises:
            AssertionError: If the recorded result is not True.
        """
        assert self.result is True

    async def and_mr_state_should_be_removed(self):
        """
        Assert that the merge request with iid 42 is present in the queue and
        its status is "removed".

        Raises:
            AssertionError: If the MR state is missing or its "status" is not
            "removed".
        """
        state = await self.queue.get_mr_state(42)
        assert state is not None
        assert state["status"] == "removed"

    async def and_queue_should_be_empty(self):
        """
        Assert that the queue contains no items.

        Raises:
            AssertionError: if the queue length is not zero.
        """
        length = await self.queue.get_queue_length()
        assert length == 0

    async def do_cleanup(self):
        """
        Exit the test database context created for the scenario and release its
        resources.

        Performs asynchronous teardown by calling the database context
        manager's async exit to close connections and clean up the temporary
        test database.
        """
        await self._db_context.__aexit__(None, None, None)
