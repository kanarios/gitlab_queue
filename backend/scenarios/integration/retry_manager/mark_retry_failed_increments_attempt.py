"""Test that mark_retry_failed increments attempt count and keeps item in queue."""

from __future__ import annotations

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database

from ._helpers import create_test_payload, create_test_retry_manager


class Scenario(vedro.Scenario):
    subject = "mark retry failed increments attempt count"

    async def given_event_in_retry_queue(self):
        self._db_ctx = initialized_test_database()
        self.db = await self._db_ctx.__aenter__()
        self.manager = create_test_retry_manager(
            self.db,
            max_attempts=3,
            base_delay_seconds=0,
        )
        await self.manager.ensure_schema()
        self.retry_id = await self.manager.add_to_retry_queue(
            event_type="merge_request",
            payload=create_test_payload(),
            error="initial error",
        )

    async def when_retry_is_marked_failed(self):
        self.moved_to_dlq = await self.manager.mark_retry_failed(
            self.retry_id,
            "error on attempt 1",
        )

    def then_should_not_be_moved_to_dlq(self):
        assert self.moved_to_dlq is False, "Expected False (not moved to DLQ), got True"

    async def and_item_should_still_be_in_queue_with_incremented_attempt(self):
        # Use a new manager with base_delay_seconds=0 to read the updated item
        # because the backoff may have pushed next_attempt_at into the future
        reader = create_test_retry_manager(self.db, base_delay_seconds=0)
        ready_events = await reader.get_events_ready_for_retry()
        assert len(ready_events) == 1, f"Expected 1 event still in queue, got {len(ready_events)}"
        item = ready_events[0]
        assert item.attempt_count == 1, f"Expected attempt_count=1, got {item.attempt_count}"
        assert item.last_error == "error on attempt 1"

    async def do_cleanup(self):
        await self._db_ctx.__aexit__(None, None, None)
