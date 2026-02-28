"""Test that cleanup_old_dlq_entries removes expired entries."""

from __future__ import annotations

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database
from sqlalchemy import text

from ._helpers import create_test_payload, create_test_retry_manager


class Scenario(vedro.Scenario):
    subject = "cleanup old dlq entries removes expired entries"

    async def given_backdated_dlq_entries(self):
        """
        Prepare test database and insert two dead-letter queue entries timestamped 60 days in the past.

        Creates a test retry manager, adds two failed DLQ entries, and adjusts their moved_to_dlq_at timestamps to be 60 days earlier so they qualify as expired for cleanup tests.
        """
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
        """
        Invoke cleanup_old_dlq_entries with a 30-day threshold and record the number of deleted DLQ entries.

        Stores the resulting deleted-entry count on self.deleted_count.
        """
        self.deleted_count = await self.manager.cleanup_old_dlq_entries(days=30)

    def then_all_entries_should_be_deleted(self):
        """
        Assert that exactly two DLQ entries were deleted during the cleanup step.

        Raises:
            AssertionError: if self.deleted_count is not 2; the assertion message includes the actual deleted count.
        """
        assert self.deleted_count == 2, f"Expected 2 deleted entries, got {self.deleted_count}"

    async def and_dlq_should_be_empty(self):
        """
        Verify the dead-letter queue contains no entries after cleanup.

        Asserts that retrieving DLQ entries from self.manager yields an empty list; raises an AssertionError with message "Expected 0 DLQ entries after cleanup, got {n}" if any entries remain.
        """
        entries = await self.manager.get_dlq_entries()
        assert len(entries) == 0, f"Expected 0 DLQ entries after cleanup, got {len(entries)}"

    async def and_cleanup_with_large_days_should_delete_nothing(self):
        # Add another entry (it will have the current timestamp)
        """
        Verifies that running cleanup_old_dlq_entries with a very large day threshold does not remove recently-added DLQ entries.

        Adds a new DLQ entry with the current timestamp, invokes cleanup_old_dlq_entries(days=99999), and asserts that zero entries are deleted and exactly one DLQ entry remains.
        """
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
        """
        Close the test database context used by the scenario.

        Performs asynchronous cleanup of resources allocated for the scenario's test database.
        """
        await self._db_ctx.__aexit__(None, None, None)
