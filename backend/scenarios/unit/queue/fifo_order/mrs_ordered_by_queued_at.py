"""Test scenario: MRs are ordered by queued_at timestamp."""

import asyncio

import vedro

from gitlab_queue.core.queue import QueueManager
from scenarios.contexts.sqlite_client import initialized_test_database

from ._helpers import create_test_mr


class Scenario(vedro.Scenario):
    subject = "MRs are ordered by queued_at timestamp"

    async def given_queue_with_mrs_added_in_sequence(self):
        self._db_context = initialized_test_database()
        self.db = await self._db_context.__aenter__()
        self.queue = QueueManager(db=self.db)
        await self.queue.ensure_schema()
        # Add MRs with delays to ensure distinct timestamps
        self.iid_order = [10, 20, 30]
        for iid in self.iid_order:
            mr = create_test_mr(iid=iid, title=f"MR {iid}")
            await self.queue.add_to_queue(99999, mr)
            await asyncio.sleep(0.01)

    async def when_active_queue_is_retrieved(self):
        self.active_queue = await self.queue.get_active_queue()

    def then_order_should_match_insertion_order(self):
        """
        Asserts that the active queue's MR iids match the original insertion order.

        Builds a list of mr_iid values from the current active queue and raises an AssertionError if that list differs from the recorded insertion order (self.iid_order).
        """
        actual_order = [item.mr_iid for item in self.active_queue]
        assert actual_order == self.iid_order

    async def do_cleanup(self):
        """
        Exit the scenario's test database context and release associated resources.

        Calls the asynchronous context-exit on the stored _db_context to close the connection and perform cleanup.
        """
        await self._db_context.__aexit__(None, None, None)
