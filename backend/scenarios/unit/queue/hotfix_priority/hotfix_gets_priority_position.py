"""Test that hotfix MR gets priority position over regular MRs."""

import asyncio

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database

from gitlab_queue.core.queue import QueueManager

from ._helpers import create_test_mr


class Scenario(vedro.Scenario):
    subject = "hotfix MR gets priority position over regular MRs"

    async def given_queue_with_regular_mrs(self):
        self._db_context = initialized_test_database()
        self.db = await self._db_context.__aenter__()
        self.queue = QueueManager(db=self.db)
        await self.queue.ensure_schema()
        # Add regular MRs first
        for iid in [1, 2, 3]:
            mr = create_test_mr(iid=iid, title=f"Regular MR {iid}")
            await self.queue.add_to_queue(mr, is_hotfix=False)
            await asyncio.sleep(0.01)  # Ensure distinct queued_at

    async def when_hotfix_mr_is_added(self):
        hotfix = create_test_mr(iid=99, title="Hotfix MR")
        self.hotfix_item = await self.queue.add_to_queue(hotfix, is_hotfix=True)

    async def then_hotfix_should_be_at_position_1(self):
        position = await self.queue.get_queue_position(99)
        assert position == 1

    async def and_regular_mrs_should_shift_positions(self):
        for iid in [1, 2, 3]:
            position = await self.queue.get_queue_position(iid)
            expected = iid + 1  # Shifted by 1 due to hotfix
            assert position == expected

    async def do_cleanup(self):
        await self._db_context.__aexit__(None, None, None)
