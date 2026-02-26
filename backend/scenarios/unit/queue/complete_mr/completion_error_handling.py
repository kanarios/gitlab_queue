"""Test scenario: complete_mr returns false when MR already moved to history."""

from __future__ import annotations

import vedro

from gitlab_queue.core.queue import QueueManager
from scenarios.contexts.sqlite_client import initialized_test_database

from ._helpers import create_test_mr


class Scenario(vedro.Scenario):
    subject = "complete mr returns false when MR already moved to history"

    async def given_mr_already_in_history(self):
        """
        Ensure a test merge request with IID 42 is present in history before the scenario runs.

        Initializes a test SQLite database context and assigns self._db_context, self.db, and self.queue; ensures the queue schema exists, creates and enqueues a test MR with IID 42, updates its state to "merged", and calls complete_mr to move it into history (asserts the first completion succeeds).
        """
        self._db_context = initialized_test_database()
        self.db = await self._db_context.__aenter__()
        self.queue = QueueManager(db=self.db)
        await self.queue.ensure_schema()

        mr = create_test_mr(iid=42)
        await self.queue.add_to_queue(mr)
        await self.queue.update_mr_state(42, "merged")
        # First completion moves MR to history
        first_result = await self.queue.complete_mr(42, "merged")
        assert first_result is True

    async def when_mr_is_completed_again(self):
        # Second completion should return False since MR is no longer in active queue
        """
        Attempts to complete the merge request with id 42 a second time and records the outcome.

        Stores the boolean result of the completion attempt in self.result: `True` if completion succeeded, `False` otherwise.
        """
        self.result = await self.queue.complete_mr(42, "merged")

    def then_result_should_be_false(self):
        """
        Assert that the most recent MR completion attempt returned False.

        Raises:
            AssertionError: If `self.result` is not `False`.
        """
        assert self.result is False

    async def and_history_record_should_still_exist(self):
        """
        Verify that the merge request with ID 42 remains recorded in history with status "merged".

        Asserts that the MR state is present and that its "status" field equals "merged".
        """
        state = await self.queue.get_mr_state(42)
        assert state is not None
        assert state["status"] == "merged"

    async def do_cleanup(self):
        """
        Close and clean up the test database context used by the scenario.

        This finalizes and releases resources associated with the scenario's database context.
        """
        await self._db_context.__aexit__(None, None, None)
