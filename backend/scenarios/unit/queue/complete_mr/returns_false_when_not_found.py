"""Test scenario: complete_mr returns False when MR not found."""

from __future__ import annotations

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database

from gitlab_queue.core.queue import QueueManager


class Scenario(vedro.Scenario):
    subject = "complete mr returns false when mr not found"

    async def given_empty_queue(self):
        """
        Prepare an empty queue backed by a test SQLite database.
        
        Initializes a test database context, enters it to obtain and store the database handle on self.db, creates a QueueManager using that handle (stored on self.queue), and ensures the queue schema exists. The test database context is retained on self._db_context for later cleanup.
        """
        self._db_context = initialized_test_database()
        self.db = await self._db_context.__aenter__()
        self.queue = QueueManager(db=self.db)
        await self.queue.ensure_schema()

    async def when_completing_nonexistent_mr(self):
        """
        Attempts to complete a merge request with ID 999 using status "merged" and stores the boolean outcome in self.result.
        """
        self.result = await self.queue.complete_mr(999, "merged")

    def then_result_should_be_false(self):
        """
        Asserts that the stored result is False.
        
        This test step verifies that the operation under test produced a boolean False value.
        """
        assert self.result is False

    async def do_cleanup(self):
        """
        Exit the asynchronous test database context used by the scenario.
        
        This closes the database context entered during setup to release resources and perform cleanup.
        """
        await self._db_context.__aexit__(None, None, None)
