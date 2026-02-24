"""Test scenario: complete_mr handles duplicate history insertion gracefully."""

from __future__ import annotations

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database

from gitlab_queue.core.queue import QueueManager

from ._helpers import create_test_mr


class Scenario(vedro.Scenario):
    subject = "complete mr returns false on duplicate history race condition"

    async def given_mr_already_in_history(self):
        self._db_context = initialized_test_database()
        self.db = await self._db_context.__aenter__()
        self.queue = QueueManager(db=self.db)
        await self.queue.ensure_schema()

        mr = create_test_mr(iid=42)
        await self.queue.add_to_queue(mr)
        await self.queue.update_mr_state(42, "merged")
        # First completion moves MR to history
        first_result = await self.queue.complete_mr(42, "merged")
        assert first_result is True, "First completion should succeed"

    async def when_mr_is_completed_again(self):
        # Second completion should return False since MR is no longer in active queue
        self.result = await self.queue.complete_mr(42, "merged")

    def then_result_should_be_false(self):
        assert self.result is False, f"Expected False for duplicate completion, got {self.result}"

    async def and_history_record_should_still_exist(self):
        state = await self.queue.get_mr_state(42)
        assert state is not None, "Expected MR to remain in history"
        assert state["status"] == "merged", f"Expected 'merged', got {state['status']}"

    async def do_cleanup(self):
        if hasattr(self, "_db_context"):
            await self._db_context.__aexit__(None, None, None)
