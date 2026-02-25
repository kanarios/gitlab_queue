"""Test scenario: remove already removed MR is idempotent."""

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database

from gitlab_queue.core.queue import QueueManager

from ._helpers import create_test_mr


class Scenario(vedro.Scenario):
    subject = "remove already removed MR is idempotent"

    async def given_queue_with_removed_mr(self):
        self._db_context = initialized_test_database()
        self.db = await self._db_context.__aenter__()
        self.queue = QueueManager(db=self.db)
        await self.queue.ensure_schema()
        mr = create_test_mr(iid=42)
        await self.queue.add_to_queue(mr)
        # Remove it once
        await self.queue.remove_from_queue(42)

    async def when_mr_is_removed_again(self):
        """
        Attempts to remove merge request with ID 42 from the queue a second time.
        
        Stores the boolean outcome on self.result: `True` if the call removed the MR, `False` if the MR was already removed.
        """
        self.result = await self.queue.remove_from_queue(42)

    def then_result_should_be_false(self):
        """
        Verify that the previous removal attempt indicated no change.
        
        Raises:
            AssertionError: If the stored result is not False.
        """
        assert self.result is False

    async def and_mr_state_should_still_be_removed(self):
        """
        Verifies that the merge request with id 42 remains marked as removed in the queue.
        
        Asserts that the MR state exists and that its `status` field is "removed".
        """
        state = await self.queue.get_mr_state(42)
        assert state is not None
        assert state["status"] == "removed"

    async def do_cleanup(self):
        await self._db_context.__aexit__(None, None, None)
