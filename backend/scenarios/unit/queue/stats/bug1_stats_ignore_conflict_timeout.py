"""BUG-1: Stats ignore conflict/timeout statuses in total_completed."""

from __future__ import annotations

import vedro

from gitlab_queue.core.queue import QueueManager
from scenarios.contexts.sqlite_client import initialized_test_database

from ._helpers import create_test_mr


class Scenario(vedro.Scenario):
    subject = "dashboard stats count conflict and timeout in total_completed"

    async def given_queue_with_all_terminal_statuses(self):
        self._db_context = initialized_test_database()
        self.db = await self._db_context.__aenter__()
        self.queue = QueueManager(db=self.db)
        await self.queue.ensure_schema()

        # Add 4 MRs, complete each with a different status
        for iid, status in [(1, "merged"), (2, "failed"), (3, "conflict"), (4, "timeout")]:
            mr = create_test_mr(iid=iid, title=f"MR {iid}")
            await self.queue.add_to_queue(99999, mr)
            await self.queue.complete_mr(99999, iid, status=status)

    async def when_dashboard_stats_are_retrieved(self):
        self.stats = await self.queue.get_dashboard_stats(days=7)

    def then_total_completed_should_be_4(self):
        # merged_count + failed_count = total_completed
        total = self.stats.merged_count + self.stats.failed_count
        assert total == 4, f"Expected total_completed=4, got {total}"

    def and_success_rate_should_be_25(self):
        assert self.stats.success_rate == 25.0, f"Expected 25.0, got {self.stats.success_rate}"

    async def do_cleanup(self):
        await self._db_context.__aexit__(None, None, None)
