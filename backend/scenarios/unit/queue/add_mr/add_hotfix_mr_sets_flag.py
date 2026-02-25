"""Test scenario for adding hotfix MR with is_hotfix flag."""

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database

from gitlab_queue.core.queue import QueueManager

from ._helpers import create_test_mr


class Scenario(vedro.Scenario):
    subject = "add hotfix mr sets is_hotfix flag"

    async def given_empty_queue(self):
        self._db_context = initialized_test_database()
        self.db = await self._db_context.__aenter__()
        self.queue = QueueManager(db=self.db)
        await self.queue.ensure_schema()

    async def when_hotfix_mr_is_added(self):
        """
        Adds a test merge request marked as a hotfix to the queue and stores the resulting queue item on self.
        
        Creates a test MR with iid=42 and title "Hotfix MR", enqueues it with is_hotfix=True, and assigns the returned queue item to self.item.
        """
        mr = create_test_mr(iid=42, title="Hotfix MR")
        self.item = await self.queue.add_to_queue(mr, is_hotfix=True)

    def then_item_should_have_hotfix_flag(self):
        """
        Assert that the stored queue item has its hotfix flag set.
        """
        assert self.item.is_hotfix is True

    async def and_item_should_be_retrievable_with_flag(self):
        """
        Verifies that a queue item with id 42 can be retrieved and has its is_hotfix flag set to True.
        
        Checks that the retrieved item is present and that its `is_hotfix` attribute is `True`.
        """
        retrieved = await self.queue.get_queue_item(42)
        assert retrieved is not None
        assert retrieved.is_hotfix is True

    async def do_cleanup(self):
        await self._db_context.__aexit__(None, None, None)
