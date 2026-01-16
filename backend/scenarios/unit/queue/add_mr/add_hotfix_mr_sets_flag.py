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
        mr = create_test_mr(iid=42, title="Hotfix MR")
        self.item = await self.queue.add_to_queue(mr, is_hotfix=True)

    def then_item_should_have_hotfix_flag(self):
        assert self.item.is_hotfix is True, f"Expected is_hotfix=True, got {self.item.is_hotfix}"

    async def and_item_should_be_retrievable_with_flag(self):
        retrieved = await self.queue.get_queue_item(42)
        assert retrieved is not None
        assert retrieved.is_hotfix is True

    async def do_cleanup(self):
        await self._db_context.__aexit__(None, None, None)
