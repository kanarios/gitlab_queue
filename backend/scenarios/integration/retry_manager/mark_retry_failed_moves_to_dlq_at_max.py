"""Test that mark_retry_failed moves item to DLQ when max attempts reached."""

from __future__ import annotations

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database

from ._helpers import create_test_payload, create_test_retry_manager


class Scenario(vedro.Scenario):
    subject = "mark retry failed moves item to dlq at max attempts"

    async def given_event_in_retry_queue_with_max_attempts_1(self):
        self._db_ctx = initialized_test_database()
        self.db = await self._db_ctx.__aenter__()
        self.manager = create_test_retry_manager(
            self.db,
            max_attempts=1,
            base_delay_seconds=0,
        )
        await self.manager.ensure_schema()
        self.retry_id = await self.manager.add_to_retry_queue(
            event_type="merge_request",
            payload=create_test_payload(),
            error="initial error",
        )

    async def when_retry_is_marked_failed(self):
        ready = await self.manager.get_events_ready_for_retry()
        assert len(ready) == 1, f"Expected 1 ready event, got {len(ready)}"
        self.moved_to_dlq = await self.manager.mark_retry_failed(
            self.retry_id,
            "final error",
        )

    def then_should_be_moved_to_dlq(self):
        assert self.moved_to_dlq is True, "Expected True (moved to DLQ), got False"

    async def and_retry_queue_should_be_empty(self):
        ready = await self.manager.get_events_ready_for_retry()
        assert len(ready) == 0, f"Expected 0 events in retry queue after DLQ move, got {len(ready)}"

    async def and_dlq_should_have_the_entry(self):
        dlq_entries = await self.manager.get_dlq_entries()
        assert len(dlq_entries) == 1, f"Expected 1 DLQ entry, got {len(dlq_entries)}"
        entry = dlq_entries[0]
        assert entry.event_type == "merge_request"
        assert entry.last_error == "final error"
        assert entry.attempt_count == 1

    async def do_cleanup(self):
        await self._db_ctx.__aexit__(None, None, None)
