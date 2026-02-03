"""Test scenario: get_stale_mrs returns MRs queued longer than threshold."""

from __future__ import annotations

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database
from sqlalchemy import text

from gitlab_queue.core.queue import QueueManager

from ._helpers import create_test_mr


class Scenario(vedro.Scenario):
    subject = "get stale mrs returns old queued mrs"

    async def given_queue_with_old_mr(self):
        self._db_context = initialized_test_database()
        self.db = await self._db_context.__aenter__()
        self.queue = QueueManager(db=self.db)
        await self.queue.ensure_schema()

        mr = create_test_mr(iid=42)
        await self.queue.add_to_queue(mr)

        # Manually set queued_at to 2 hours ago via raw SQL
        async with self.db.transaction() as session:
            await session.execute(
                text("UPDATE merge_requests SET queued_at = datetime('now', '-2 hours') WHERE iid = :iid"),
                {"iid": 42},
            )

    async def when_stale_mrs_are_retrieved(self):
        self.stale = await self.queue.get_stale_mrs(hours=1)

    def then_should_return_the_old_mr(self):
        assert len(self.stale) == 1, f"Expected 1 stale MR, got {len(self.stale)}"
        assert self.stale[0].mr_iid == 42, f"Expected MR 42, got MR {self.stale[0].mr_iid}"

    async def do_cleanup(self):
        await self._db_context.__aexit__(None, None, None)
