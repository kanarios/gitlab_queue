"""BUG-2: History misses conflict/timeout MRs."""

from __future__ import annotations

import vedro

from gitlab_queue.core.queue import QueueManager
from scenarios.contexts.sqlite_client import initialized_test_database

from ._helpers import create_test_mr


class Scenario(vedro.Scenario):
    subject = "recent history includes conflict and timeout MRs"

    async def given_queue_with_all_terminal_statuses(self):
        self._db_context = initialized_test_database()
        self.db = await self._db_context.__aenter__()
        self.queue = QueueManager(db=self.db)
        await self.queue.ensure_schema()

        # Add 5 MRs, complete each with a different status
        for iid, status in [
            (1, "merged"),
            (2, "failed"),
            (3, "removed"),
            (4, "conflict"),
            (5, "timeout"),
        ]:
            mr = create_test_mr(iid=iid, title=f"MR {iid}")
            await self.queue.add_to_queue(mr)
            await self.queue.complete_mr(iid, status=status)

    async def when_recent_history_is_retrieved(self):
        self.history = await self.queue.get_recent_history(limit=10)

    def then_should_return_all_5_mrs(self):
        assert len(self.history) == 5, f"Expected 5 items, got {len(self.history)}"

    def and_should_include_all_statuses(self):
        statuses = {item.state for item in self.history}
        assert statuses == {"merged", "failed", "removed", "conflict", "timeout"}, (
            f"Expected all 5 statuses, got {statuses}"
        )

    async def do_cleanup(self):
        await self._db_context.__aexit__(None, None, None)
