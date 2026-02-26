"""Test that hotfix MR gets priority position over regular MRs."""

import asyncio

import vedro

from gitlab_queue.core.queue import QueueManager
from scenarios.contexts.sqlite_client import initialized_test_database

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
        """
        Assert that the hotfix merge request with IID 99 occupies queue position 1.

        Raises:
            AssertionError: If the MR's queue position is not 1.
        """
        position = await self.queue.get_queue_position(99)
        assert position == 1

    async def and_regular_mrs_should_shift_positions(self):
        """
        Asserts that regular merge requests were shifted one position back after a hotfix was added.

        Checks queue positions for MRs with IIDs 1, 2, and 3 and verifies each equals its IID plus 1, confirming they were moved down by one slot.
        """
        for iid in [1, 2, 3]:
            position = await self.queue.get_queue_position(iid)
            expected = iid + 1  # Shifted by 1 due to hotfix
            assert position == expected

    async def do_cleanup(self):
        """
        Close the test database context and release its resources.

        This exits the asynchronous database context manager used by the scenario to ensure connections and temporary state are cleaned up.
        """
        await self._db_context.__aexit__(None, None, None)
