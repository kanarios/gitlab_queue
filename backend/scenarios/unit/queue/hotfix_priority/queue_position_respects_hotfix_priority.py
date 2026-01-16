"""Test that queue position calculation respects hotfix priority."""

import asyncio

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database

from gitlab_queue.core.queue import QueueManager

from ._helpers import create_test_mr


class Scenario(vedro.Scenario):
    subject = "queue position calculation respects hotfix priority"

    async def given_mixed_queue(self):
        self._db_context = initialized_test_database()
        self.db = await self._db_context.__aenter__()
        self.queue = QueueManager(db=self.db)
        await self.queue.ensure_schema()
        # Add: regular1, hotfix1, regular2, hotfix2
        regular1 = create_test_mr(iid=1, title="Regular 1")
        await self.queue.add_to_queue(regular1, is_hotfix=False)
        await asyncio.sleep(0.01)

        hotfix1 = create_test_mr(iid=2, title="Hotfix 1")
        await self.queue.add_to_queue(hotfix1, is_hotfix=True)
        await asyncio.sleep(0.01)

        regular2 = create_test_mr(iid=3, title="Regular 2")
        await self.queue.add_to_queue(regular2, is_hotfix=False)
        await asyncio.sleep(0.01)

        hotfix2 = create_test_mr(iid=4, title="Hotfix 2")
        await self.queue.add_to_queue(hotfix2, is_hotfix=True)

    async def when_all_positions_are_queried(self):
        self.positions = {}
        for iid in [1, 2, 3, 4]:
            self.positions[iid] = await self.queue.get_queue_position(iid)

    def then_positions_should_reflect_hotfix_priority(self):
        # Expected order: hotfix1(2), hotfix2(4), regular1(1), regular2(3)
        assert self.positions[2] == 1, f"Hotfix 1 expected at 1, got {self.positions[2]}"
        assert self.positions[4] == 2, f"Hotfix 2 expected at 2, got {self.positions[4]}"
        assert self.positions[1] == 3, f"Regular 1 expected at 3, got {self.positions[1]}"
        assert self.positions[3] == 4, f"Regular 2 expected at 4, got {self.positions[3]}"

    async def and_active_queue_should_be_in_correct_order(self):
        active = await self.queue.get_active_queue()
        expected_order = [2, 4, 1, 3]  # hotfixes first, then regulars, each group FIFO
        actual_order = [item.mr_iid for item in active]
        assert actual_order == expected_order, f"Expected {expected_order}, got {actual_order}"

    async def do_cleanup(self):
        await self._db_context.__aexit__(None, None, None)
