"""Test that retry_dlq_entry moves item back from DLQ to retry queue."""

from __future__ import annotations

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database

from ._helpers import create_test_payload, create_test_retry_manager


class Scenario(vedro.Scenario):
    subject = "retry dlq entry moves item back to retry queue"

    async def given_dlq_entry(self):
        self._db_ctx = initialized_test_database()
        self.db = await self._db_ctx.__aenter__()
        self.manager = create_test_retry_manager(
            self.db,
            max_attempts=1,
            base_delay_seconds=0,
        )
        await self.manager.ensure_schema()

        self.payload = create_test_payload()
        retry_id = await self.manager.add_to_retry_queue(
            event_type="merge_request",
            payload=self.payload,
            error="initial error",
        )
        await self.manager.mark_retry_failed(retry_id, "final error")

        dlq_entries = await self.manager.get_dlq_entries()
        self.dlq_id = dlq_entries[0].id

    async def when_dlq_entry_is_retried(self):
        self.new_retry_id = await self.manager.retry_dlq_entry(self.dlq_id)

    def then_new_retry_id_should_be_positive(self):
        assert self.new_retry_id > 0, f"Expected new retry_id > 0, got {self.new_retry_id}"

    async def and_dlq_should_be_empty(self):
        dlq_entries = await self.manager.get_dlq_entries()
        assert len(dlq_entries) == 0, f"Expected 0 DLQ entries after retry, got {len(dlq_entries)}"

    async def and_retry_queue_should_have_the_item(self):
        ready_events = await self.manager.get_events_ready_for_retry()
        assert len(ready_events) == 1, f"Expected 1 event in retry queue, got {len(ready_events)}"
        item = ready_events[0]
        assert item.id == self.new_retry_id
        assert item.event_type == "merge_request"
        assert item.payload == self.payload
        assert item.attempt_count == 0

    async def do_cleanup(self):
        await self._db_ctx.__aexit__(None, None, None)
