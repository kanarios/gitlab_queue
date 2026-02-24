"""Test that multiple hotfixes are ordered by queued_at within hotfix group."""

import asyncio

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database

from gitlab_queue.core.queue import QueueManager

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
            await self.queue.add_to_queue(mr, is_hotfix=True)
            await asyncio.sleep(0.01)  # Ensure distinct queued_at

    async def when_positions_are_queried(self):
        self.positions = {}
        for iid in [10, 20, 30]:
            self.positions[iid] = await self.queue.get_queue_position(iid)

    def then_hotfixes_should_be_in_fifo_order(self):
        assert self.positions[10] == 1, f"First hotfix expected at 1, got {self.positions[10]}"
        assert self.positions[20] == 2, f"Second hotfix expected at 2, got {self.positions[20]}"
        assert self.positions[30] == 3, f"Third hotfix expected at 3, got {self.positions[30]}"

    async def do_cleanup(self):
        if hasattr(self, "_db_context"):
            await self._db_context.__aexit__(None, None, None)
