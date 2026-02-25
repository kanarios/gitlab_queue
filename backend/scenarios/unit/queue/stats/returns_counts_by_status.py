"""Test scenario: get_queue_stats returns counts grouped by status."""

from __future__ import annotations

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database

from gitlab_queue.core.queue import QueueManager

from ._helpers import create_test_mr


class Scenario(vedro.Scenario):
    subject = "get queue stats returns counts by status"

    async def given_queue_with_mixed_statuses(self):
        """
        Set up a test queue with two merge requests in different statuses.
        
        Initializes a test SQLite database and QueueManager, ensures the queue schema exists, enqueues two test merge requests (IID 1 and IID 2), and updates the state of the merge request with IID 2 to "testing" so that one MR remains queued and the other is in testing.
        """
        self._db_context = initialized_test_database()
        self.db = await self._db_context.__aenter__()
        self.queue = QueueManager(db=self.db)
        await self.queue.ensure_schema()

        # Add two MRs: one stays queued, one moves to testing
        mr1 = create_test_mr(iid=1, title="MR 1")
        mr2 = create_test_mr(iid=2, title="MR 2")
        await self.queue.add_to_queue(mr1)
        await self.queue.add_to_queue(mr2)
        await self.queue.update_mr_state(2, "testing")

    async def when_stats_are_retrieved(self):
        """
        Retrieve queue statistics and assign them to self.stats.
        
        The fetched value is the mapping of queue statuses to their counts and is stored on the scenario instance for later assertions.
        """
        self.stats = await self.queue.get_queue_stats()

    def then_queued_count_should_be_1(self):
        assert self.stats["queued"] == 1

    def and_testing_count_should_be_1(self):
        """
        Asserts that the queue statistics report exactly one item with status "testing".
        
        Raises:
            AssertionError: If the 'testing' count is not 1.
        """
        assert self.stats["testing"] == 1

    def and_rebasing_count_should_be_0(self):
        """
        Asserts that the 'rebasing' count in the retrieved queue stats equals 0.
        """
        assert self.stats["rebasing"] == 0

    def and_merging_count_should_be_0(self):
        """
        Asserts that the retrieved queue statistics report zero items in the "merging" status.
        
        Raises:
            AssertionError: If the "merging" count is not 0.
        """
        assert self.stats["merging"] == 0

    async def do_cleanup(self):
        """
        Exit the test database context and release associated resources.
        
        This cleans up the initialized test SQLite database context used by the scenario.
        """
        await self._db_context.__aexit__(None, None, None)
