"""Test that get_dlq_entries returns paginated results."""

from __future__ import annotations

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database

from ._helpers import create_test_payload, create_test_retry_manager


class Scenario(vedro.Scenario):
    subject = "get dlq entries returns paginated results"

    async def given_three_dlq_entries(self):
        """
        Set up a test database and retry manager, then populate the dead-letter queue with three failed entries.

        Initializes an asynchronous test database context and a RetryManager configured for tests, ensures its schema exists, and inserts three retry entries (each marked as failed) with event_type "merge_request" and test payloads so subsequent steps can verify pagination behavior.
        """
        self._db_ctx = initialized_test_database()
        self.db = await self._db_ctx.__aenter__()
        self.manager = create_test_retry_manager(
            self.db,
            max_attempts=1,
            base_delay_seconds=0,
        )
        await self.manager.ensure_schema()

        for i in range(3):
            retry_id = await self.manager.add_to_retry_queue(
                event_type="merge_request",
                payload=create_test_payload(),
                error=f"error {i}",
            )
            await self.manager.mark_retry_failed(retry_id, f"final error {i}")

    async def when_dlq_entries_fetched_with_limit_2(self):
        """
        Fetch up to two dead-letter queue (DLQ) entries and store them on the scenario's `entries` attribute.

        This step populates `self.entries` with the retrieved DLQ entries (at most two) for subsequent assertions.
        """
        self.entries = await self.manager.get_dlq_entries(limit=2)

    def then_two_entries_should_be_returned(self):
        """
        Asserts that exactly two DLQ entries were returned for a limit of 2.

        Raises:
            AssertionError: If the number of entries in self.entries is not 2.
        """
        assert len(self.entries) == 2, f"Expected 2 DLQ entries (limit=2), got {len(self.entries)}"

    async def and_all_three_entries_should_exist(self):
        """
        Asserts that exactly three dead-letter queue (DLQ) entries exist.

        Fetches DLQ entries with a limit of 50 and raises an AssertionError if the total number of entries is not 3.
        """
        all_entries = await self.manager.get_dlq_entries(limit=50)
        assert len(all_entries) == 3, f"Expected 3 total DLQ entries, got {len(all_entries)}"

    async def do_cleanup(self):
        """
        Exit the test database context to release and clean up database resources.

        This awaits the async context manager's __aexit__ to close the test database connection acquired in setup.
        """
        await self._db_ctx.__aexit__(None, None, None)
