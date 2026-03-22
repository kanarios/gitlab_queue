"""Test that multiple hotfixes are ordered by queued_at within hotfix group."""

import asyncio

import vedro

from gitlab_queue.core.queue import QueueManager
from scenarios.contexts.sqlite_client import initialized_test_database

from ._helpers import create_test_mr


class Scenario(vedro.Scenario):
    subject = "multiple hotfixes are ordered by queued_at within hotfix group"

    async def given_queue_with_multiple_hotfixes(self):
        self._db_context = initialized_test_database()
        self.db = await self._db_context.__aenter__()
        self.queue = QueueManager(db=self.db)
        await self.queue.ensure_schema()
        # Add hotfixes in order
        for iid in [10, 20, 30]:
            mr = create_test_mr(iid=iid, title=f"Hotfix {iid}")
            await self.queue.add_to_queue(99999, mr, is_hotfix=True)
            await asyncio.sleep(0.01)  # Ensure distinct queued_at

    async def when_positions_are_queried(self):
        """
        Populate self.positions with queue positions for test hotfix IIDs 10, 20, and 30.

        Each key is an IID and its value is the result of calling the queue's get_queue_position for that IID.
        """
        self.positions = {}
        for iid in [10, 20, 30]:
            self.positions[iid] = await self.queue.get_queue_position(99999, iid)

    def then_hotfixes_should_be_in_fifo_order(self):
        """
        Verify that hotfix merge requests are ordered by queued position in FIFO order within the hotfix group.

        Asserts that the merge requests with IIDs 10, 20, and 30 have queue positions 1, 2, and 3 respectively.
        """
        assert self.positions[10] == 1
        assert self.positions[20] == 2
        assert self.positions[30] == 3

    async def do_cleanup(self):
        """
        Tears down the test database context and performs asynchronous cleanup.

        This method exits the underlying asynchronous database context manager to release resources created for the test.
        """
        await self._db_context.__aexit__(None, None, None)
