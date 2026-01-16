"""Test scenario: get_active_queue returns MRs in FIFO order."""

import asyncio

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database

from gitlab_queue.core.queue import QueueManager

from ._helpers import create_test_mr


class Scenario(vedro.Scenario):
    subject = "get_active_queue returns MRs in FIFO order"

    async def given_queue_with_mrs_in_various_states(self):
        self._db_context = initialized_test_database()
        self.db = await self._db_context.__aenter__()
        self.queue = QueueManager(db=self.db)
        await self.queue.ensure_schema()
        # Add 5 MRs
        for iid in [1, 2, 3, 4, 5]:
            mr = create_test_mr(iid=iid)
            await self.queue.add_to_queue(mr)
            await asyncio.sleep(0.01)
        # Change some states (but they remain in active queue)
        await self.queue.update_mr_state(2, "rebasing")
        await self.queue.update_mr_state(4, "testing")

    async def when_active_queue_is_retrieved(self):
        self.active_queue = await self.queue.get_active_queue()

    def then_all_active_mrs_should_be_in_fifo_order(self):
        actual_order = [item.mr_iid for item in self.active_queue]
        expected_order = [1, 2, 3, 4, 5]
        assert actual_order == expected_order, f"Expected {expected_order}, got {actual_order}"

    def and_queue_should_have_5_items(self):
        assert len(self.active_queue) == 5

    async def do_cleanup(self):
        await self._db_context.__aexit__(None, None, None)
