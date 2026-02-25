"""Test that get_dlq_entries filters by event_type."""

from __future__ import annotations

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database

from ._helpers import create_test_payload, create_test_retry_manager


class Scenario(vedro.Scenario):
    subject = "get dlq entries filters by event type"

    async def given_dlq_entries_of_different_types(self):
        """
        Seed the test context with dead-letter queue (DLQ) entries of different event types.
        
        Initializes a test database context and retry manager, ensures the schema exists, then adds two failed DLQ entries with event_type "merge_request" and one failed DLQ entry with event_type "pipeline". Sets self._db_ctx, self.db, and self.manager for use by subsequent scenario steps.
        """
        self._db_ctx = initialized_test_database()
        self.db = await self._db_ctx.__aenter__()
        self.manager = create_test_retry_manager(
            self.db,
            max_attempts=1,
            base_delay_seconds=0,
        )
        await self.manager.ensure_schema()

        # Add 2 merge_request events
        for i in range(2):
            retry_id = await self.manager.add_to_retry_queue(
                event_type="merge_request",
                payload=create_test_payload("merge_request"),
                error=f"mr error {i}",
            )
            await self.manager.mark_retry_failed(retry_id, f"mr final error {i}")

        # Add 1 pipeline event
        retry_id = await self.manager.add_to_retry_queue(
            event_type="pipeline",
            payload=create_test_payload("pipeline"),
            error="pipeline error",
        )
        await self.manager.mark_retry_failed(retry_id, "pipeline final error")

    async def when_dlq_entries_filtered_by_merge_request(self):
        """
        Filter dead-letter queue entries by event_type "merge_request" and store the results on the scenario.
        
        Sets self.filtered_entries to the list of DLQ entries whose event_type equals "merge_request".
        """
        self.filtered_entries = await self.manager.get_dlq_entries(
            event_type="merge_request",
        )

    def then_only_merge_request_entries_should_be_returned(self):
        """
        Assert that the filtered entries contain exactly two items and every entry has event_type equal to "merge_request".
        
        Raises:
            AssertionError: If the number of entries is not two or if any entry's event_type is not "merge_request".
        """
        assert len(self.filtered_entries) == 2, f"Expected 2 merge_request entries, got {len(self.filtered_entries)}"
        for entry in self.filtered_entries:
            assert entry.event_type == "merge_request", f"Expected event_type='merge_request', got '{entry.event_type}'"

    async def do_cleanup(self):
        """
        Exit and clean up the test database context used by the scenario.
        
        Closes the async database context manager opened during setup so resources are released.
        """
        await self._db_ctx.__aexit__(None, None, None)
