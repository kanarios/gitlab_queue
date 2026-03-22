"""Test scenario: get_stale_mrs returns MRs queued longer than threshold."""

from __future__ import annotations

import vedro

from gitlab_queue.core.queue import QueueManager
from scenarios.contexts.sqlite_client import initialized_test_database

from ._helpers import backfill_queued_at_hours_ago, create_test_mr


class Scenario(vedro.Scenario):
    subject = "get stale mrs returns old queued mrs"

    async def given_queue_with_old_mr(self):
        """
        Prepare a test queue containing a merge request queued two hours ago.

        Initializes a test database context, creates a QueueManager and ensures its schema, enqueues a test merge request with iid 42, and backfills its `queued_at` timestamp to two hours in the past. The test database context, database handle, and queue manager are stored on `self` as `_db_context`, `db`, and `queue`.
        """
        self._db_context = initialized_test_database()
        self.db = await self._db_context.__aenter__()
        self.queue = QueueManager(db=self.db)
        await self.queue.ensure_schema()

        mr = create_test_mr(iid=42)
        await self.queue.add_to_queue(99999, mr)

        await backfill_queued_at_hours_ago(self.db, iid=42, hours=2)

    async def when_stale_mrs_are_retrieved(self):
        """
        Retrieve merge requests that have been queued for more than one hour and store them on the scenario.

        self.stale will contain a list of merge request records queued more than one hour ago.
        """
        self.stale = await self.queue.get_stale_mrs(99999, hours=1)

    def then_should_return_the_old_mr(self):
        """
        Asserts that exactly one stale merge request is returned and that its IID is 42.

        Raises an AssertionError if the number of stale MRs is not 1 or if the returned MR's `mr_iid` is not 42.
        """
        assert len(self.stale) == 1
        assert self.stale[0].mr_iid == 42

    async def do_cleanup(self):
        """
        Exit the scenario's async database context and release associated resources.

        This closes the test database context opened during setup so connections and other resources are cleaned up.
        """
        await self._db_context.__aexit__(None, None, None)
