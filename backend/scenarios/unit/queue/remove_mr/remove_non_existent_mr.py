"""Test scenario: remove non-existent MR."""

import vedro

from gitlab_queue.core.queue import QueueManager
from scenarios.contexts.sqlite_client import initialized_test_database


class Scenario(vedro.Scenario):
    subject = "remove non-existent MR"

    async def given_empty_queue(self):
        self._db_context = initialized_test_database()
        self.db = await self._db_context.__aenter__()
        self.queue = QueueManager(db=self.db)
        await self.queue.ensure_schema()

    async def when_nonexistent_mr_is_removed(self):
        """
        Attempts to remove a merge request with ID 999 from the queue and stores the operation result on self.result.

        The stored value will indicate whether the removal succeeded (`True`) or failed (`False`).
        """
        self.result = await self.queue.remove_from_queue(999)

    def then_result_should_be_false(self):
        """
        Assert that the previously stored result is False.

        Raises:
            AssertionError: If `self.result` is not `False`.
        """
        assert self.result is False

    async def and_queue_should_still_be_empty(self):
        """
        Assert that the queue contains no items.

        Raises:
            AssertionError: if the queue length is not zero.
        """
        length = await self.queue.get_queue_length()
        assert length == 0

    async def do_cleanup(self):
        """
        Exit the test database context to release resources used by the scenario.

        This method asynchronously exits the internal database context manager, performing any necessary cleanup after the scenario runs.
        """
        await self._db_context.__aexit__(None, None, None)
