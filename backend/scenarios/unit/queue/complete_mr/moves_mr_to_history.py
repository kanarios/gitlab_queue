"""Test scenario: complete_mr moves MR from active queue to history."""

from __future__ import annotations

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database

from gitlab_queue.core.queue import QueueManager

from ._helpers import create_test_mr


class Scenario(vedro.Scenario):
    subject = "complete mr moves mr to history"

    async def given_queue_with_merged_mr(self):
        """
        Prepare a test queue containing a merge request (MR) with IID 42 marked as merged.
        
        Initializes a test SQLite database context, creates a QueueManager bound to that database, ensures the queue schema exists, adds a test MR with IID 42 to the active queue, and records its state as "merged". Exposes the database context as self._db_context, the open database connection as self.db, and the queue manager as self.queue for later steps in the scenario.
        """
        self._db_context = initialized_test_database()
        self.db = await self._db_context.__aenter__()
        self.queue = QueueManager(db=self.db)
        await self.queue.ensure_schema()

        mr = create_test_mr(iid=42)
        await self.queue.add_to_queue(mr)
        await self.queue.update_mr_state(42, "merged")

    async def when_mr_is_completed(self):
        """
        Complete merge request with IID 42 using the "merged" state and store the outcome.
        
        Invokes the queue's completion operation for MR 42 and assigns the returned result to self.result.
        """
        self.result = await self.queue.complete_mr(42, "merged")

    def then_result_should_be_true(self):
        """
        Assert that the previously stored result is `True`.
        
        Raises:
            AssertionError: If `self.result` is not `True`.
        """
        assert self.result is True

    async def and_mr_should_be_removed_from_active_queue(self):
        """
        Asserts that the merge request with id 42 is no longer present in the active queue.
        
        Raises:
            AssertionError: If a queue item for MR id 42 still exists.
        """
        item = await self.queue.get_queue_item(42)
        assert item is None

    async def and_mr_should_exist_in_history(self):
        """
        Asserts that merge request with ID 42 exists in history and has status "merged".
        
        Retrieves the stored MR state for ID 42 and verifies it is present and its `status` equals "merged".
        """
        state = await self.queue.get_mr_state(42)
        assert state is not None
        assert state["status"] == "merged"

    async def do_cleanup(self):
        """
        Tear down the test database context and release its resources.
        
        Exits the asynchronous database context entered during setup, closing the underlying connection and cleaning up temporary test state.
        """
        await self._db_context.__aexit__(None, None, None)
