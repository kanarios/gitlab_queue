"""Test scenario: mark_stale_warning_sent excludes MR from stale results."""

from __future__ import annotations

import vedro

from gitlab_queue.core.queue import QueueManager
from scenarios.contexts.sqlite_client import initialized_test_database

from ._helpers import backfill_queued_at_hours_ago, create_test_mr


class Scenario(vedro.Scenario):
    subject = "mark stale warning sent excludes mr from stale results"

    async def given_queue_with_stale_mr(self):
        """
        Set up a test queue populated with a stale merge request (IID 42).

        Initializes a test database context and stores it on self._db_context and self.db, creates a QueueManager on self.queue and ensures its schema, enqueues a test MR with IID 42, and backfills its queued_at timestamp to two hours ago so it appears stale.
        """
        self._db_context = initialized_test_database()
        self.db = await self._db_context.__aenter__()
        self.queue = QueueManager(db=self.db)
        await self.queue.ensure_schema()

        mr = create_test_mr(iid=42)
        await self.queue.add_to_queue(99999, mr)

        await backfill_queued_at_hours_ago(self.db, iid=42, hours=2)

    async def when_stale_warning_is_marked(self):
        """
        Mark the stale-warning flag as sent for the merge request with IID 42 and record the operation result on the scenario.

        This step invokes the queue manager to mark the stale warning as sent for MR 42 and stores the boolean result in `self.mark_result`.
        """
        self.mark_result = await self.queue.mark_stale_warning_sent(99999, 42)

    def then_mark_result_should_be_true(self):
        """
        Assert that the stale-warning marking operation returned True.

        Raises:
            AssertionError: If the stored mark result is not True.
        """
        assert self.mark_result is True

    async def and_stale_mrs_should_be_empty(self):
        """
        Asserts that no merge requests are considered stale within the last hour.

        Fetches stale MRs for a 1-hour window and fails the test if any are returned.
        """
        stale = await self.queue.get_stale_mrs(99999, hours=1)
        assert len(stale) == 0

    async def do_cleanup(self):
        """
        Close and clean up the test database context used by the scenario.

        Performs any asynchronous teardown required by the underlying database context and releases associated resources.
        """
        await self._db_context.__aexit__(None, None, None)
