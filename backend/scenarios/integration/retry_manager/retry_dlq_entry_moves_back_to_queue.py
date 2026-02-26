"""Test that retry_dlq_entry moves item back from DLQ to retry queue."""

from __future__ import annotations

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database

from ._helpers import create_test_payload, create_test_retry_manager


class Scenario(vedro.Scenario):
    subject = "retry dlq entry moves item back to retry queue"

    async def given_dlq_entry(self):
        """
        Prepare a dead-letter-queue entry by inserting a failed retry item and capturing its DLQ id.

        Initializes a test database and retry manager, ensures the schema, creates a test payload, enqueues a retry for event_type "merge_request", marks that retry as failed so it appears in the DLQ, and stores the created payload on self.payload and the DLQ entry id on self.dlq_id.
        """
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
        """
        Retries the dead-letter-queue entry referenced by self.dlq_id and records the resulting retry identifier.

        After execution, self.new_retry_id contains the identifier of the newly created retry entry.
        """
        self.new_retry_id = await self.manager.retry_dlq_entry(self.dlq_id)

    def then_new_retry_id_should_be_positive(self):
        """
        Asserts that the new retry identifier is greater than zero.

        Raises:
            AssertionError: If `self.new_retry_id` is not greater than zero; the message includes the actual value.
        """
        assert self.new_retry_id > 0, f"Expected new retry_id > 0, got {self.new_retry_id}"

    async def and_dlq_should_be_empty(self):
        """
        Asserts that the dead-letter queue contains no entries after retrying an item.

        Raises an AssertionError if one or more DLQ entries remain, including the actual count in the message.
        """
        dlq_entries = await self.manager.get_dlq_entries()
        assert len(dlq_entries) == 0, f"Expected 0 DLQ entries after retry, got {len(dlq_entries)}"

    async def and_retry_queue_should_have_the_item(self):
        """
        Assert that the retry queue contains exactly the retried item with the expected id, event type, payload, and zero attempts.

        Raises:
            AssertionError: If the retry queue does not contain exactly one ready event or if the event's id, event_type, payload, or attempt_count do not match the expected values.
        """
        ready_events = await self.manager.get_events_ready_for_retry()
        assert len(ready_events) == 1, f"Expected 1 event in retry queue, got {len(ready_events)}"
        item = ready_events[0]
        assert item.id == self.new_retry_id
        assert item.event_type == "merge_request"
        assert item.payload == self.payload
        assert item.attempt_count == 0

    async def do_cleanup(self):
        """
        Close and release the asynchronous database context associated with the scenario.

        Exits the internal async context manager (self._db_ctx) to ensure the test database connection and related resources are cleaned up.
        """
        await self._db_ctx.__aexit__(None, None, None)
