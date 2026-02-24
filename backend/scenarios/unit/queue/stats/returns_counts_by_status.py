"""Test scenario: get_queue_stats returns counts grouped by status."""

from __future__ import annotations

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database

from gitlab_queue.core.queue import QueueManager

from ._helpers import create_test_mr


class Scenario(vedro.Scenario):
    subject = "get queue stats returns counts by status"

    async def given_queue_with_mixed_statuses(self):
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
        self.stats = await self.queue.get_queue_stats()

    def then_queued_count_should_be_1(self):
        assert self.stats["queued"] == 1, f"Expected 1 queued, got {self.stats['queued']}"

    def and_testing_count_should_be_1(self):
        assert self.stats["testing"] == 1, f"Expected 1 testing, got {self.stats['testing']}"

    def and_rebasing_count_should_be_0(self):
        assert self.stats["rebasing"] == 0, f"Expected 0 rebasing, got {self.stats['rebasing']}"

    def and_merging_count_should_be_0(self):
        assert self.stats["merging"] == 0, f"Expected 0 merging, got {self.stats['merging']}"

    async def do_cleanup(self):
        if hasattr(self, "_db_context"):
            await self._db_context.__aexit__(None, None, None)
