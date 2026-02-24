"""Test scenario: mark_stale_warning_sent excludes MR from stale results."""

from __future__ import annotations

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database
from sqlalchemy import text

from gitlab_queue.core.queue import QueueManager

from ._helpers import create_test_mr


class Scenario(vedro.Scenario):
    subject = "mark stale warning sent excludes mr from stale results"

    async def given_queue_with_stale_mr(self):
        self._db_context = initialized_test_database()
        self.db = await self._db_context.__aenter__()
        self.queue = QueueManager(db=self.db)
        await self.queue.ensure_schema()

        mr = create_test_mr(iid=42)
        await self.queue.add_to_queue(mr)

        # Make MR stale by setting queued_at to 2 hours ago
        async with self.db.transaction() as session:
            await session.execute(
                text("UPDATE merge_requests SET queued_at = datetime('now', '-2 hours') WHERE iid = :iid"),
                {"iid": 42},
            )

    async def when_stale_warning_is_marked(self):
        self.mark_result = await self.queue.mark_stale_warning_sent(42)

    def then_mark_result_should_be_true(self):
        assert self.mark_result is True, f"Expected True, got {self.mark_result}"

    async def and_stale_mrs_should_be_empty(self):
        stale = await self.queue.get_stale_mrs(hours=1)
        assert len(stale) == 0, f"Expected 0 stale MRs after marking, got {len(stale)}"

    async def do_cleanup(self):
        if hasattr(self, "_db_context"):
            await self._db_context.__aexit__(None, None, None)
