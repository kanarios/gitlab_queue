"""Test scenario: get_mr_state returns None for unknown MR."""

from __future__ import annotations

import vedro

from gitlab_queue.core.queue import QueueManager
from scenarios.contexts.sqlite_client import initialized_test_database


class Scenario(vedro.Scenario):
    subject = "get mr state returns none when not found"

    async def given_empty_queue(self):
        """
        Prepare an empty QueueManager backed by a test database and ensure its schema exists.

        Initializes an in-memory test database context, enters it to obtain a DB handle, constructs a QueueManager using that DB, and creates the required schema so the queue is ready for testing.
        """
        self._db_context = initialized_test_database()
        self.db = await self._db_context.__aenter__()
        self.queue = QueueManager(db=self.db)
        await self.queue.ensure_schema()

    async def when_state_is_retrieved_for_unknown_mr(self):
        """
        Retrieve the merge request state for a non-existent MR and store it on the scenario.

        Calls the queue's get_mr_state for MR id 999 and assigns the result to self.state for later assertions.
        """
        self.state = await self.queue.get_mr_state(999)

    def then_state_should_be_none(self):
        """
        Validate that the retrieved merge request state is absent.

        Asserts that self.state is None.
        """
        assert self.state is None

    async def do_cleanup(self):
        """
        Exit the database context used by the scenario to release resources.

        This finalizer closes the underlying test database context created during setup so connection and related resources are cleaned up.
        """
        await self._db_context.__aexit__(None, None, None)
