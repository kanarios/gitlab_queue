"""Test scenario: get_mr_state returns state for active queue item."""

from __future__ import annotations

import vedro

from gitlab_queue.core.queue import QueueManager
from scenarios.contexts.sqlite_client import initialized_test_database

from ._helpers import create_test_mr


class Scenario(vedro.Scenario):
    subject = "get mr state returns active state"

    async def given_queue_with_mr(self):
        """
        Prepare a test queue containing a merge request with iid 42.

        Initializes an asynchronous test database context and stores the context manager on `self._db_context`, binds and stores the database handle on `self.db`, constructs a `QueueManager` stored on `self.queue`, ensures the queue schema exists, creates a test merge request with iid 42, and adds it to the queue.
        """
        self._db_context = initialized_test_database()
        self.db = await self._db_context.__aenter__()
        self.queue = QueueManager(db=self.db)
        await self.queue.ensure_schema()

        mr = create_test_mr(iid=42)
        await self.queue.add_to_queue(mr)

    async def when_state_is_retrieved(self):
        """
        Retrieve the merge request state for IID 42 and store it on self.state.

        After execution, self.state will contain the MR state dictionary if found, otherwise None.
        """
        self.state = await self.queue.get_mr_state(42)

    def then_state_should_not_be_none(self):
        """
        Asserts that the previously retrieved merge request state is present.

        Raises:
            AssertionError: If `self.state` is None.
        """
        assert self.state is not None

    def and_status_should_be_queued(self):
        """
        Check that the retrieved merge request state has status "queued".

        Raises:
            AssertionError: If the state's "status" is not "queued".
        """
        assert self.state["status"] == "queued"

    async def do_cleanup(self):
        """
        Exit the asynchronous test database context opened during setup.

        Closes the context manager that provides the test database connection used by the scenario.
        """
        await self._db_context.__aexit__(None, None, None)
