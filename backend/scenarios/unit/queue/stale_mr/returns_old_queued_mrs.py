"""Test scenario: get_stale_mrs returns MRs queued longer than threshold."""

from __future__ import annotations

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database

from gitlab_queue.core.queue import QueueManager

from ._helpers import backfill_queued_at_hours_ago, create_test_mr


class Scenario(vedro.Scenario):
    subject = "get stale mrs returns old queued mrs"

    async def given_queue_with_old_mr(self):
        self._db_context = initialized_test_database()
        self.db = await self._db_context.__aenter__()
        self.queue = QueueManager(db=self.db)
        await self.queue.ensure_schema()

        mr = create_test_mr(iid=42)
        await self.queue.add_to_queue(mr)

        await backfill_queued_at_hours_ago(self.db, iid=42, hours=2)

    async def when_stale_mrs_are_retrieved(self):
        self.stale = await self.queue.get_stale_mrs(hours=1)

    def then_should_return_the_old_mr(self):
        assert len(self.stale) == 1
        assert self.stale[0].mr_iid == 42

    async def do_cleanup(self):
        await self._db_context.__aexit__(None, None, None)
