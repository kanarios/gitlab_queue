"""Test scenario: removed MR has no active queue position."""

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database

from gitlab_queue.core.queue import QueueManager

from ._helpers import create_test_mr


class Scenario(vedro.Scenario):
    subject = "removed MR has no active queue position"

    async def given_queue_with_removed_mr(self):
        self._db_context = initialized_test_database()
        self.db = await self._db_context.__aenter__()
        self.queue = QueueManager(db=self.db)
        await self.queue.ensure_schema()
        mr = create_test_mr(iid=42)
        await self.queue.add_to_queue(mr)
        await self.queue.remove_from_queue(42)

    async def when_position_is_queried(self):
        self.position = await self.queue.get_queue_position(42)

    def then_position_should_be_none(self):
        assert self.position is None

    async def and_active_queue_should_be_empty(self):
        active = await self.queue.get_active_queue()
        assert len(active) == 0

    async def and_mr_should_still_exist_in_db(self):
        item = await self.queue.get_queue_item(42)
        assert item is not None
        assert item.state == "removed"

    async def do_cleanup(self):
        await self._db_context.__aexit__(None, None, None)
