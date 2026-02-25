"""Test scenario: position calculation reflects FIFO order."""

import asyncio

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database

from gitlab_queue.core.queue import QueueManager

from ._helpers import create_test_mr


class Scenario(vedro.Scenario):
    subject = "position calculation reflects FIFO order"

    async def given_queue_with_three_mrs(self):
        self._db_context = initialized_test_database()
        self.db = await self._db_context.__aenter__()
        self.queue = QueueManager(db=self.db)
        await self.queue.ensure_schema()
        # Add MRs in order: 5, 15, 25
        for iid in [5, 15, 25]:
            mr = create_test_mr(iid=iid)
            await self.queue.add_to_queue(mr)
            await asyncio.sleep(0.01)

    async def when_positions_are_queried(self):
        """
        Query and store queue positions for merge requests with iids 5, 15, and 25.
        
        Populates or replaces self.positions with a dict mapping each iid to its current position in the queue (e.g. {5: pos5, 15: pos15, 25: pos25}).
        """
        self.positions = {}
        for iid in [5, 15, 25]:
            self.positions[iid] = await self.queue.get_queue_position(iid)

    def then_positions_should_reflect_insertion_order(self):
        """
        Assert that stored positions reflect FIFO insertion order.
        
        Checks that merge requests with iids 5, 15, and 25 have queue positions 1, 2, and 3 respectively.
        """
        assert self.positions[5] == 1
        assert self.positions[15] == 2
        assert self.positions[25] == 3

    async def and_removing_first_should_shift_positions(self):
        """
        Verify that removing the first merge request shifts queue positions of the remaining items.
        
        Removes the MR with iid 5 from the queue and asserts that the MR with iid 15 is at position 1 and the MR with iid 25 is at position 2.
        """
        await self.queue.remove_from_queue(5)
        pos_15 = await self.queue.get_queue_position(15)
        pos_25 = await self.queue.get_queue_position(25)
        assert pos_15 == 1
        assert pos_25 == 2

    async def do_cleanup(self):
        """
        Exit and clean up the test database context used by the scenario.
        
        This asynchronously finalizes and closes the underlying database context manager held in
        self._db_context.
        """
        await self._db_context.__aexit__(None, None, None)
