"""Test scenario: get_active_queue returns MRs in FIFO order."""

import vedro

from gitlab_queue.core.queue import QueueManager
from scenarios.contexts.sqlite_client import initialized_test_database

from ._helpers import create_test_mr


class Scenario(vedro.Scenario):
    subject = "get_active_queue returns MRs in FIFO order"

    async def given_queue_with_mrs_in_various_states(self):
        """
        Prepare a test database and queue populated with five merge requests, with two MR states changed.

        Sets up an initialized test database and a QueueManager, ensures the schema, adds merge requests with iids 1-5 to the queue, and updates the state of MR 2 to "rebasing" and MR 4 to "testing". The updated MRs remain part of the active queue.
        """
        self._db_context = initialized_test_database()
        self.db = await self._db_context.__aenter__()
        self.queue = QueueManager(db=self.db)
        await self.queue.ensure_schema()
        # Add 5 MRs
        for iid in [1, 2, 3, 4, 5]:
            mr = create_test_mr(iid=iid)
            await self.queue.add_to_queue(99999, mr)
        # Change some states (but they remain in active queue)
        await self.queue.update_mr_state(99999, 2, "rebasing")
        await self.queue.update_mr_state(99999, 4, "testing")

    async def when_active_queue_is_retrieved(self):
        self.active_queue = await self.queue.get_active_queue(99999)

    def then_all_active_mrs_should_be_in_fifo_order(self):
        """
        Asserts that the active queue's merge requests are in FIFO order with iids 1 through 5.

        Raises:
            AssertionError: If the extracted MR iids from self.active_queue do not equal [1, 2, 3, 4, 5].
        """
        actual_order = [item.mr_iid for item in self.active_queue]
        expected_order = [1, 2, 3, 4, 5]
        assert actual_order == expected_order

    def and_queue_should_have_5_items(self):
        """
        Assert the active queue contains exactly five merge requests.
        """
        assert len(self.active_queue) == 5

    async def do_cleanup(self):
        await self._db_context.__aexit__(None, None, None)
