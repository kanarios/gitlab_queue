"""Test scenario: get_next_mr returns oldest queued MR."""

import asyncio

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database

from gitlab_queue.core.queue import QueueManager

from ._helpers import create_test_mr


class Scenario(vedro.Scenario):
    subject = "get_next_mr returns oldest queued MR"

    async def given_queue_with_multiple_mrs(self):
        self._db_context = initialized_test_database()
        self.db = await self._db_context.__aenter__()
        self.queue = QueueManager(db=self.db)
        await self.queue.ensure_schema()
        # Add MRs in specific order
        for iid in [100, 200, 300]:
            mr = create_test_mr(iid=iid, title=f"MR {iid}")
            await self.queue.add_to_queue(mr)
            await asyncio.sleep(0.01)

    async def when_next_mr_is_requested(self):
        self.next_item = await self.queue.get_next_mr()

    def then_oldest_mr_should_be_returned(self):
        assert self.next_item is not None
        assert self.next_item.mr_iid == 100

    async def and_subsequent_calls_return_same_until_state_change(self):
        # get_next_mr returns status='queued' only, so calling again returns same
        second_next = await self.queue.get_next_mr()
        assert second_next is not None
        assert second_next.mr_iid == 100

    async def do_cleanup(self):
        await self._db_context.__aexit__(None, None, None)
