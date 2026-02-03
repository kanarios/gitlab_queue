"""Test that add_to_retry_queue creates an entry and returns a valid id."""

from __future__ import annotations

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database

from ._helpers import create_test_payload, create_test_retry_manager


class Scenario(vedro.Scenario):
    subject = "add to retry queue creates entry with valid id"

    async def given_retry_manager(self):
        self._db_ctx = initialized_test_database()
        self.db = await self._db_ctx.__aenter__()
        self.manager = create_test_retry_manager(self.db, base_delay_seconds=0)
        await self.manager.ensure_schema()

    async def when_event_is_added_to_retry_queue(self):
        self.payload = create_test_payload()
        self.retry_id = await self.manager.add_to_retry_queue(
            event_type="merge_request",
            payload=self.payload,
            error="connection timeout",
        )

    def then_retry_id_should_be_positive(self):
        assert self.retry_id > 0, f"Expected retry_id > 0, got {self.retry_id}"

    async def and_entry_should_be_retrievable(self):
        ready_events = await self.manager.get_events_ready_for_retry()
        assert len(ready_events) == 1, f"Expected 1 ready event, got {len(ready_events)}"
        item = ready_events[0]
        assert item.id == self.retry_id
        assert item.event_type == "merge_request"
        assert item.payload == self.payload
        assert item.attempt_count == 0
        assert item.last_error == "connection timeout"

    async def do_cleanup(self):
        await self._db_ctx.__aexit__(None, None, None)
