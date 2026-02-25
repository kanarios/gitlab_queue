"""Test scenario for adding MR to empty queue."""

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database
from scenarios.library import QueueState

from gitlab_queue.core.queue import QueueManager

from ._helpers import create_test_mr


class Scenario(vedro.Scenario):
    subject = "add mr to empty queue"

    async def given_empty_queue(self):
        self._db_context = initialized_test_database()
        self.db = await self._db_context.__aenter__()
        self.queue = QueueManager(db=self.db)
        await self.queue.ensure_schema()

    async def when_mr_is_added(self):
        self.mr = create_test_mr(iid=42)
        self.item = await self.queue.add_to_queue(self.mr)

    async def then_item_should_be_at_position_1(self):
        position = await self.queue.get_queue_position(42)
        assert position == 1

    def and_state_should_be_queued(self):
        assert self.item.state == QueueState.QUEUED

    def and_mr_data_should_match(self):
        assert self.item.mr_iid == 42
        assert self.item.title == "Test MR"
        assert self.item.author_name == "Test User"
        assert self.item.author_username == "testuser"

    async def do_cleanup(self):
        await self._db_context.__aexit__(None, None, None)
