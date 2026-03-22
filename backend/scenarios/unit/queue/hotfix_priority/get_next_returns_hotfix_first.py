"""Test that get_next_mr returns hotfix before regular MRs."""

import asyncio

import vedro

from gitlab_queue.core.queue import QueueManager
from scenarios.contexts.sqlite_client import initialized_test_database

from ._helpers import create_test_mr


class Scenario(vedro.Scenario):
    subject = "get_next_mr returns hotfix before regular MRs"

    async def given_queue_with_mixed_priority(self):
        self._db_context = initialized_test_database()
        self.db = await self._db_context.__aenter__()
        self.queue = QueueManager(db=self.db)
        await self.queue.ensure_schema()
        # Add regular MR first
        regular = create_test_mr(iid=1, title="Regular MR")
        await self.queue.add_to_queue(99999, regular, is_hotfix=False)
        await asyncio.sleep(0.01)
        # Add hotfix second (but should be returned first)
        hotfix = create_test_mr(iid=2, title="Hotfix MR")
        await self.queue.add_to_queue(99999, hotfix, is_hotfix=True)

    async def when_next_mr_is_requested(self):
        self.next_item = await self.queue.get_next_mr(99999)

    def then_hotfix_should_be_returned(self):
        assert self.next_item is not None
        assert self.next_item.mr_iid == 2
        assert self.next_item.is_hotfix is True

    async def do_cleanup(self):
        """Clean up the test DB context."""
        await self._db_context.__aexit__(None, None, None)
