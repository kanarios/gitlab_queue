"""Test that cleanup_old_dlq_entries removes expired entries."""

from __future__ import annotations

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database
from sqlalchemy import text

from ._helpers import create_test_payload, create_test_retry_manager


class Scenario(vedro.Scenario):
    subject = "cleanup old dlq entries removes expired entries"

    async def given_backdated_dlq_entries(self):
        self._db_ctx = initialized_test_database()
        self.db = await self._db_ctx.__aenter__()
        self.manager = create_test_retry_manager(
            self.db,
            max_attempts=1,
            base_delay_seconds=0,
        )
        await self.manager.ensure_schema()

        # Create 2 DLQ entries
        for i in range(2):
            retry_id = await self.manager.add_to_retry_queue(
                event_type="merge_request",
                payload=create_test_payload(),
                error=f"error {i}",
            )
            await self.manager.mark_retry_failed(retry_id, f"final error {i}")

        # Backdate the DLQ entries to 60 days ago so cleanup can find them
        async with self.db.transaction() as session:
            await session.execute(text("UPDATE webhook_dlq SET moved_to_dlq_at = datetime('now', '-60 days')"))

    async def when_cleanup_is_called_with_30_days(self):
        self.deleted_count = await self.manager.cleanup_old_dlq_entries(days=30)

    def then_all_entries_should_be_deleted(self):
        assert self.deleted_count == 2, f"Expected 2 deleted entries, got {self.deleted_count}"

    async def and_dlq_should_be_empty(self):
        entries = await self.manager.get_dlq_entries()
        assert len(entries) == 0, f"Expected 0 DLQ entries after cleanup, got {len(entries)}"

    async def and_cleanup_with_large_days_should_delete_nothing(self):
        # Add another entry (it will have the current timestamp)
        retry_id = await self.manager.add_to_retry_queue(
            event_type="merge_request",
            payload=create_test_payload(),
            error="new error",
        )
        await self.manager.mark_retry_failed(retry_id, "new final error")

        # Cleanup with days=99999 should not delete anything
        deleted = await self.manager.cleanup_old_dlq_entries(days=99999)
        assert deleted == 0, f"Expected 0 deleted with days=99999, got {deleted}"

        entries = await self.manager.get_dlq_entries()
        assert len(entries) == 1, f"Expected 1 DLQ entry remaining, got {len(entries)}"

    async def do_cleanup(self):
        await self._db_ctx.__aexit__(None, None, None)
