"""Test that mark_retry_success removes the entry from the queue."""

from __future__ import annotations

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database

from ._helpers import create_test_payload, create_test_retry_manager


class Scenario(vedro.Scenario):
    subject = "mark retry success removes entry from queue"

    async def given_event_in_retry_queue(self):
        self._db_ctx = initialized_test_database()
        self.db = await self._db_ctx.__aenter__()
        self.manager = create_test_retry_manager(self.db, base_delay_seconds=0)
        await self.manager.ensure_schema()
        self.retry_id = await self.manager.add_to_retry_queue(
            event_type="merge_request",
            payload=create_test_payload(),
            error="transient error",
        )

    async def when_retry_is_marked_successful(self):
        await self.manager.mark_retry_success(self.retry_id)

    async def then_queue_should_be_empty(self):
        ready_events = await self.manager.get_events_ready_for_retry()
        assert len(ready_events) == 0

    async def do_cleanup(self):
        await self._db_ctx.__aexit__(None, None, None)
