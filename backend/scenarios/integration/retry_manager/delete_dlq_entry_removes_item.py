"""Test that delete_dlq_entry removes the item from the DLQ."""

from __future__ import annotations

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database

from ._helpers import create_test_payload, create_test_retry_manager


class Scenario(vedro.Scenario):
    subject = "delete dlq entry removes item from dlq"

    async def given_dlq_entry(self):
        self._db_ctx = initialized_test_database()
        self.db = await self._db_ctx.__aenter__()
        self.manager = create_test_retry_manager(
            self.db,
            max_attempts=1,
            base_delay_seconds=0,
        )
        await self.manager.ensure_schema()

        retry_id = await self.manager.add_to_retry_queue(
            event_type="merge_request",
            payload=create_test_payload(),
            error="some error",
        )
        await self.manager.mark_retry_failed(retry_id, "final error")

        dlq_entries = await self.manager.get_dlq_entries()
        self.dlq_id = dlq_entries[0].id

    async def when_dlq_entry_is_deleted(self):
        self.deleted = await self.manager.delete_dlq_entry(self.dlq_id)

    def then_delete_should_return_true(self):
        assert self.deleted is True, "Expected delete to return True"

    async def and_dlq_should_be_empty(self):
        entries = await self.manager.get_dlq_entries()
        assert len(entries) == 0, f"Expected 0 DLQ entries after deletion, got {len(entries)}"

    async def do_cleanup(self):
        await self._db_ctx.__aexit__(None, None, None)
