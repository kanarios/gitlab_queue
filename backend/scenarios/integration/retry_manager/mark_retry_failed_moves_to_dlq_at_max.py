"""Test that mark_retry_failed moves item to DLQ when max attempts reached."""

from __future__ import annotations

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database

from ._helpers import create_test_payload, create_test_retry_manager


class Scenario(vedro.Scenario):
    subject = "mark retry failed moves item to dlq at max attempts"

    async def given_event_in_retry_queue_with_max_attempts_1(self):
        """
        Prepare test state by inserting a retryable event into the retry queue configured with max attempts = 1.

        Opens a test SQLite database context, creates a retry manager with max_attempts set to 1 and base_delay_seconds set to 0, ensures the retry schema exists, and enqueues a "merge_request" event with a test payload and an initial error. Stores the database context, database handle, manager, and created retry entry id on the test instance for use by later steps.
        """
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
        """
        Marks the prepared retry entry as failed and records whether it was moved to the dead-letter queue.

        Asserts that exactly one event is ready for retry, then marks the entry identified by self.retry_id as failed with a final error and stores the boolean result in self.moved_to_dlq.
        """
        ready = await self.manager.get_events_ready_for_retry()
        assert len(ready) == 1
        self.moved_to_dlq = await self.manager.mark_retry_failed(
            self.retry_id,
            "final error",
        )

    def then_should_be_moved_to_dlq(self):
        """
        Assert that the most recently processed retry entry was moved to the dead-letter queue.

        Raises:
            AssertionError: If the entry was not moved to the DLQ.
        """
        assert self.moved_to_dlq is True

    async def and_retry_queue_should_be_empty(self):
        """
        Asserts that there are no events currently ready for retry.

        Raises:
            AssertionError: If one or more events are ready for retry.
        """
        ready = await self.manager.get_events_ready_for_retry()
        assert len(ready) == 0

    async def and_dlq_should_have_the_entry(self):
        """
        Asserts the dead-letter queue contains a single entry for the test merge_request with the expected error and attempt count.

        Verifies that the DLQ has exactly one entry, that the entry's event_type equals "merge_request", last_error equals "final error", and attempt_count equals 1.
        """
        dlq_entries = await self.manager.get_dlq_entries()
        assert len(dlq_entries) == 1
        entry = dlq_entries[0]
        assert entry.event_type == "merge_request"
        assert entry.last_error == "final error"
        assert entry.attempt_count == 1

    async def do_cleanup(self):
        """
        Close the scenario's test database context.

        Performs the asynchronous exit of the database context manager created during setup.
        """
        await self._db_ctx.__aexit__(None, None, None)
