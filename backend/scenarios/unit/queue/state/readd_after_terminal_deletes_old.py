"""Test scenario: re-adding MR after terminal state deletes old record first."""

from __future__ import annotations

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database

from gitlab_queue.core.queue import QueueManager

from ._helpers import create_test_mr


class Scenario(vedro.Scenario):
    subject = "re-adding mr after terminal state deletes old record first"

    async def given_mr_in_terminal_state(self):
        self._db_context = initialized_test_database()
        self.db = await self._db_context.__aenter__()
        self.queue = QueueManager(db=self.db)
        await self.queue.ensure_schema()

        mr = create_test_mr(iid=42)
        await self.queue.add_to_queue(mr)
        # Transition to a terminal state (e.g., "failed")
        await self.queue.update_mr_state(42, "failed")

    async def when_mr_is_readded_to_queue(self):
        mr = create_test_mr(iid=42, title="Reopened MR")
        await self.queue.add_to_queue(mr)

    async def then_mr_should_exist_in_queue(self):
        self.item = await self.queue.get_queue_item(42)
        assert self.item is not None

    def and_mr_should_be_in_queued_state(self):
        assert self.item.state == "queued"

    def and_mr_title_should_be_updated(self):
        assert self.item.title == "Reopened MR"

    async def do_cleanup(self):
        await self._db_context.__aexit__(None, None, None)
