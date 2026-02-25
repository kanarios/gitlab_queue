"""Test scenario: mark_stale_warning_sent excludes MR from stale results."""

from __future__ import annotations

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database

from gitlab_queue.core.queue import QueueManager

from ._helpers import backfill_queued_at_hours_ago, create_test_mr


class Scenario(vedro.Scenario):
    subject = "mark stale warning sent excludes mr from stale results"

    async def given_queue_with_stale_mr(self):
        self._db_context = initialized_test_database()
        self.db = await self._db_context.__aenter__()
        self.queue = QueueManager(db=self.db)
        await self.queue.ensure_schema()

        mr = create_test_mr(iid=42)
        await self.queue.add_to_queue(mr)

        await backfill_queued_at_hours_ago(self.db, iid=42, hours=2)

    async def when_stale_warning_is_marked(self):
        self.mark_result = await self.queue.mark_stale_warning_sent(42)

    def then_mark_result_should_be_true(self):
        assert self.mark_result is True

    async def and_stale_mrs_should_be_empty(self):
        stale = await self.queue.get_stale_mrs(hours=1)
        assert len(stale) == 0

    async def do_cleanup(self):
        await self._db_context.__aexit__(None, None, None)
