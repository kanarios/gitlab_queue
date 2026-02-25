"""Test scenario: re-adding MR after terminal state deletes old record first."""

from __future__ import annotations

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database

from gitlab_queue.core.queue import QueueManager

from ._helpers import create_test_mr


class Scenario(vedro.Scenario):
    subject = "re-adding mr after terminal state deletes old record first"

    async def given_mr_in_terminal_state(self):
        """
        Prepare the test environment with a merge request present in a terminal state.
        
        Creates and enters a test database context, initializes the queue manager and schema, adds a test merge request with iid 42 to the queue, and transitions that merge request to the terminal state "failed".
        """
        self._db_context = initialized_test_database()
        self.db = await self._db_context.__aenter__()
        self.queue = QueueManager(db=self.db)
        await self.queue.ensure_schema()

        mr = create_test_mr(iid=42)
        await self.queue.add_to_queue(mr)
        # Transition to a terminal state (e.g., "failed")
        await self.queue.update_mr_state(42, "failed")

    async def when_mr_is_readded_to_queue(self):
        """
        Re-adds a merge request with iid 42 and an updated title to the queue.
        
        Creates a test MR with title "Reopened MR" and adds it to the scenario's queue so subsequent steps can verify re-queuing behavior.
        """
        mr = create_test_mr(iid=42, title="Reopened MR")
        await self.queue.add_to_queue(mr)

    async def then_mr_should_exist_in_queue(self):
        """
        Verify that a merge request with iid 42 exists in the queue.
        
        Retrieves the queue item with iid 42, stores it on self.item, and asserts the item is not None.
        """
        self.item = await self.queue.get_queue_item(42)
        assert self.item is not None

    def and_mr_should_be_in_queued_state(self):
        """
        Assert that the stored queue item has state "queued".
        
        Raises:
            AssertionError: If the queue item is missing or its `state` is not "queued".
        """
        assert self.item.state == "queued"

    def and_mr_title_should_be_updated(self):
        """
        Assert that the queued merge request's title equals "Reopened MR".
        
        Raises:
            AssertionError: if the item's title is not "Reopened MR".
        """
        assert self.item.title == "Reopened MR"

    async def do_cleanup(self):
        """
        Close and clean up the test database context used by the scenario.
        
        Exits the async database context manager to release connections and other resources opened during the test.
        """
        await self._db_context.__aexit__(None, None, None)
