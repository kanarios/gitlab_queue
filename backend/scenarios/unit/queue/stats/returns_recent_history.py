"""Test scenario: get_recent_history returns most recent completed MRs."""

from __future__ import annotations

import vedro

from gitlab_queue.core.queue import QueueManager
from scenarios.contexts.sqlite_client import initialized_test_database

from ._helpers import create_test_mr


class Scenario(vedro.Scenario):
    subject = "get recent history returns most recent completed mrs"

    async def given_queue_with_completed_mrs(self):
        """
        Prepare a QueueManager backed by a test database and populate it with three completed merge requests.

        Initializes a test SQLite database context and stores it on self._db_context and self.db, creates a QueueManager on self.queue and ensures its schema, then adds MRs with iids 1, 2, and 3 and marks each as merged (completed, with a finished timestamp).
        """
        self._db_context = initialized_test_database()
        self.db = await self._db_context.__aenter__()
        self.queue = QueueManager(db=self.db)
        await self.queue.ensure_schema()

        # Add and complete 3 MRs — complete_mr moves them to history table
        for iid in (1, 2, 3):
            mr = create_test_mr(iid=iid, title=f"MR {iid}")
            await self.queue.add_to_queue(mr)
            await self.queue.complete_mr(iid, status="merged")

    async def when_recent_history_is_retrieved(self):
        """
        Retrieve the most recent merge request history (limit 2) and store it on the scenario.

        This step sets self.history to the list returned by the queue's get_recent_history(limit=2).
        """
        self.history = await self.queue.get_recent_history(limit=2)

    def then_should_return_2_items(self):
        """
        Assert that the retrieved history contains exactly two items.
        """
        assert len(self.history) == 2

    def and_items_should_be_the_most_recent(self):
        """
        Assert that the retrieved history contains exactly the two most recent merge requests with iids 2 and 3.

        Raises:
            AssertionError: If the set of MR iids in self.history is not {2, 3}.
        """
        iids = {item.mr_iid for item in self.history}
        assert iids == {2, 3}

    def and_all_items_should_have_merged_status(self):
        """
        Asserts that every merge request in the retrieved history has the state "merged".

        Raises:
            AssertionError: If any item's state is not "merged".
        """
        for item in self.history:
            assert item.state == "merged"

    async def do_cleanup(self):
        """
        Close the test database context used by the scenario.

        Exits the underlying async database context manager to release connections and other resources created during setup.
        """
        await self._db_context.__aexit__(None, None, None)
