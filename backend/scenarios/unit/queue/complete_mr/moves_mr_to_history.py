"""Test scenario: complete_mr moves MR from active queue to history."""

from __future__ import annotations

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database

from gitlab_queue.core.queue import QueueManager

from ._helpers import create_test_mr


class Scenario(vedro.Scenario):
    subject = "complete mr moves mr to history"

    async def given_queue_with_merged_mr(self):
        self._db_context = initialized_test_database()
        self.db = await self._db_context.__aenter__()
        self.queue = QueueManager(db=self.db)
        await self.queue.ensure_schema()

        mr = create_test_mr(iid=42)
        await self.queue.add_to_queue(mr)
        await self.queue.update_mr_state(42, "merged")

    async def when_mr_is_completed(self):
        self.result = await self.queue.complete_mr(42, "merged")

    def then_result_should_be_true(self):
        assert self.result is True

    async def and_mr_should_be_removed_from_active_queue(self):
        item = await self.queue.get_queue_item(42)
        assert item is None

    async def and_mr_should_exist_in_history(self):
        state = await self.queue.get_mr_state(42)
        assert state is not None
        assert state["status"] == "merged"

    async def do_cleanup(self):
        await self._db_context.__aexit__(None, None, None)
