"""Test scenario for adding MR to empty queue."""

import vedro

from gitlab_queue.core.queue import QueueManager
from scenarios.contexts.sqlite_client import initialized_test_database
from scenarios.library import QueueState

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
        """
        Assert that the merge request with IID 42 occupies queue position 1.

        Raises:
            AssertionError: If the merge request's position is not 1.
        """
        position = await self.queue.get_queue_position(42)
        assert position == 1

    def and_state_should_be_queued(self):
        """
        Verify the added queue item's state is QueueState.QUEUED.

        Asserts that self.item.state is equal to QueueState.QUEUED.
        """
        assert self.item.state == QueueState.QUEUED

    def and_mr_data_should_match(self):
        """
        Asserts that the stored merge request item matches the expected test MR values.

        Checks:
        - `item.mr_iid` equals 42
        - `item.title` equals "Test MR"
        - `item.author_name` equals "Test User"
        - `item.author_username` equals "testuser"
        """
        assert self.item.mr_iid == 42
        assert self.item.title == "Test MR"
        assert self.item.author_name == "Test User"
        assert self.item.author_username == "testuser"

    async def do_cleanup(self):
        await self._db_context.__aexit__(None, None, None)
