"""Test scenario: get_dashboard_stats returns aggregate metrics."""

from __future__ import annotations

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database

from gitlab_queue.core.queue import QueueManager

from ._helpers import create_test_mr


class Scenario(vedro.Scenario):
    subject = "get dashboard stats returns aggregate metrics"

    async def given_queue_with_completed_mrs(self):
        self._db_context = initialized_test_database()
        self.db = await self._db_context.__aenter__()
        self.queue = QueueManager(db=self.db)
        await self.queue.ensure_schema()

        # Add 3 MRs, complete 2 (1 merged, 1 failed), leave 1 queued
        mr1 = create_test_mr(iid=1, title="MR 1")
        mr2 = create_test_mr(iid=2, title="MR 2")
        mr3 = create_test_mr(iid=3, title="MR 3")
        await self.queue.add_to_queue(mr1)
        await self.queue.add_to_queue(mr2)
        await self.queue.add_to_queue(mr3)

        # MR 1: queued -> testing -> merged (stays in active table with finished_at)
        await self.queue.update_mr_state(1, "testing")
        await self.queue.update_mr_state(1, "merged")

        # MR 2: queued -> testing -> failed (stays in active table with finished_at)
        await self.queue.update_mr_state(2, "testing")
        await self.queue.update_mr_state(2, "failed")

        # MR 3: stays queued (active)

    async def when_dashboard_stats_are_retrieved(self):
        self.stats = await self.queue.get_dashboard_stats(days=7)

    def then_total_in_queue_should_reflect_active_mrs(self):
        # Active queue includes queued + rebasing + testing + merging
        # MR 1 is "merged" (terminal) and MR 2 is "failed" (terminal),
        # but both are still in the active table. get_active_queue filters
        # to only active states, so only MR 3 (queued) counts.
        assert self.stats.total_in_queue == 1, f"Expected 1 active, got {self.stats.total_in_queue}"

    def and_merged_count_should_be_1(self):
        assert self.stats.merged_count == 1, f"Expected 1 merged, got {self.stats.merged_count}"

    def and_failed_count_should_be_1(self):
        assert self.stats.failed_count == 1, f"Expected 1 failed, got {self.stats.failed_count}"

    def and_success_rate_should_be_50(self):
        assert self.stats.success_rate == 50.0, f"Expected 50.0% success rate, got {self.stats.success_rate}"

    def and_stats_window_should_be_7_days(self):
        assert self.stats.stats_window_days == 7, f"Expected 7 day window, got {self.stats.stats_window_days}"

    async def do_cleanup(self):
        await self._db_context.__aexit__(None, None, None)
