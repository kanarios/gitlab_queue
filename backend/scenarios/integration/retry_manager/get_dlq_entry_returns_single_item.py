"""Test that get_dlq_entry returns a single item by id."""

from __future__ import annotations

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database

from gitlab_queue.models.retry import DLQItem

from ._helpers import create_test_payload, create_test_retry_manager


class Scenario(vedro.Scenario):
    subject = "get dlq entry returns single item by id"

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

    async def when_dlq_entry_is_fetched_by_id(self):
        self.entry = await self.manager.get_dlq_entry(self.dlq_id)

    def then_entry_should_be_a_dlq_item(self):
        assert isinstance(self.entry, DLQItem)

    def and_entry_fields_should_match(self):
        assert self.entry.id == self.dlq_id
        assert self.entry.event_type == "merge_request"
        assert self.entry.payload == self.payload
        assert self.entry.last_error == "final error"
        assert self.entry.attempt_count == 1
        assert self.entry.original_created_at is not None
        assert self.entry.moved_to_dlq_at is not None

    async def do_cleanup(self):
        await self._db_ctx.__aexit__(None, None, None)
