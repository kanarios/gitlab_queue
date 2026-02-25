"""Test scenario: get_mr_state returns state for active queue item."""

from __future__ import annotations

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database

from gitlab_queue.core.queue import QueueManager

from ._helpers import create_test_mr


class Scenario(vedro.Scenario):
    subject = "get mr state returns active state"

    async def given_queue_with_mr(self):
        self._db_context = initialized_test_database()
        self.db = await self._db_context.__aenter__()
        self.queue = QueueManager(db=self.db)
        await self.queue.ensure_schema()

        mr = create_test_mr(iid=42)
        await self.queue.add_to_queue(mr)

    async def when_state_is_retrieved(self):
        self.state = await self.queue.get_mr_state(42)

    def then_state_should_not_be_none(self):
        assert self.state is not None

    def and_status_should_be_queued(self):
        assert self.state["status"] == "queued"

    async def do_cleanup(self):
        await self._db_context.__aexit__(None, None, None)
