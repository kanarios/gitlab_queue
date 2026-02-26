"""Test scenario: get_mr_state falls back to history table."""

from __future__ import annotations

import vedro

from gitlab_queue.core.queue import QueueManager
from scenarios.contexts.sqlite_client import initialized_test_database

from ._helpers import create_test_mr


class Scenario(vedro.Scenario):
    subject = "get mr state falls back to history"

    async def given_mr_completed_to_history(self):
        """
        Prepare a test database and queue containing a merge request (iid=42) that has been completed and moved to the history table.

        This sets up:
        - an initialized asynchronous test SQLite database and QueueManager with schema ensured,
        - a test MR with iid 42 added to the active queue,
        - the MR's state updated to "testing" then "merged",
        - the MR completed (moved to the history table and removed from active).
        """
        self._db_context = initialized_test_database()
        self.db = await self._db_context.__aenter__()
        self.queue = QueueManager(db=self.db)
        await self.queue.ensure_schema()

        mr = create_test_mr(iid=42)
        await self.queue.add_to_queue(mr)
        await self.queue.update_mr_state(42, "testing")
        await self.queue.update_mr_state(42, "merged")
        # Move to history table (deletes from active)
        await self.queue.complete_mr(42, "merged")

    async def when_state_is_retrieved(self):
        """
        Retrieve the merge request state for IID 42 and store it on the scenario.

        The fetched state (or `None` if not found) is assigned to `self.state`.
        """
        self.state = await self.queue.get_mr_state(42)

    def then_state_should_not_be_none(self):
        """
        Asserts that the retrieved merge request state exists (is not None).

        Raises:
            AssertionError: If the stored `state` is None.
        """
        assert self.state is not None

    def and_status_should_be_merged(self):
        """
        Verify that the retrieved MR state's status is "merged".

        Raises:
            AssertionError: if the state's "status" field is not "merged".
        """
        assert self.state["status"] == "merged"

    def and_finished_at_should_be_set(self):
        """
        Asserts that the retrieved merge request state includes a finished_at timestamp.

        Raises:
                AssertionError: If `self.state["finished_at"]` is None.
        """
        assert self.state["finished_at"] is not None

    async def do_cleanup(self):
        """
        Exit the test database context created in the scenario.

        Ensures the asynchronous database context manager is exited so test resources are released.
        """
        await self._db_context.__aexit__(None, None, None)
