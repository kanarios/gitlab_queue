"""Test that add_to_retry_queue calculates exponential backoff correctly."""

from __future__ import annotations

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database

from ._helpers import create_test_payload, create_test_retry_manager


class Scenario(vedro.Scenario):
    subject = "add to retry queue calculates backoff delay"

    async def given_retry_manager_with_30s_delay(self):
        self._db_ctx = initialized_test_database()
        self.db = await self._db_ctx.__aenter__()
        self.manager = create_test_retry_manager(
            self.db,
            base_delay_seconds=30,
            max_delay_seconds=300,
        )
        await self.manager.ensure_schema()

    async def when_event_is_added(self):
        self.retry_id = await self.manager.add_to_retry_queue(
            event_type="merge_request",
            payload=create_test_payload(),
            error="server error",
        )

    async def then_event_should_not_be_ready_yet(self):
        ready_events = await self.manager.get_events_ready_for_retry()
        assert len(ready_events) == 0, (
            f"Expected 0 ready events (backoff is 30s in the future), got {len(ready_events)}"
        )

    async def do_cleanup(self):
        if hasattr(self, "_db_ctx"):
            await self._db_ctx.__aexit__(None, None, None)
