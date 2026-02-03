"""Test scenario: complete_mr calculates wait and processing time."""

from __future__ import annotations

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database

from gitlab_queue.core.queue import QueueManager

from ._helpers import create_test_mr


class Scenario(vedro.Scenario):
    subject = "complete mr calculates wait and processing time"

    async def given_queue_with_tested_mr(self):
        self._db_context = initialized_test_database()
        self.db = await self._db_context.__aenter__()
        self.queue = QueueManager(db=self.db)
        await self.queue.ensure_schema()

        mr = create_test_mr(iid=42)
        await self.queue.add_to_queue(mr)
        # Transition to testing sets started_at
        await self.queue.update_mr_state(42, "testing")
        # Transition to merged sets finished_at
        await self.queue.update_mr_state(42, "merged")

    async def when_mr_is_completed(self):
        self.result = await self.queue.complete_mr(42, "merged")

    def then_result_should_be_true(self):
        assert self.result is True, f"Expected True, got {self.result}"

    async def and_history_should_have_merged_status(self):
        state = await self.queue.get_mr_state(42)
        assert state is not None, "Expected MR in history, got None"
        assert state["status"] == "merged", f"Expected 'merged', got {state['status']}"

    async def and_history_should_have_finished_at(self):
        state = await self.queue.get_mr_state(42)
        assert state is not None, "Expected MR in history, got None"
        assert state["finished_at"] is not None, "Expected finished_at to be set"

    async def do_cleanup(self):
        await self._db_context.__aexit__(None, None, None)
