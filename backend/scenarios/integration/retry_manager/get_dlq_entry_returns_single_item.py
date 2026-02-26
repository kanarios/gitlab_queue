"""Test that get_dlq_entry returns a single item by id."""

from __future__ import annotations

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database

from gitlab_queue.models.retry import DLQItem

from ._helpers import create_test_payload, create_test_retry_manager


class Scenario(vedro.Scenario):
    subject = "get dlq entry returns single item by id"

    async def given_dlq_entry(self):
        """
        Set up a test dead-letter-queue (DLQ) entry and record its id on the scenario instance.

        Initializes and enters a test SQLite database context, creates a retry manager (max_attempts=1, no base delay), ensures the schema, creates and enqueues a test payload for event_type "merge_request", marks that retry as failed with the final error "final error", and stores the resulting DLQ entry id on self.dlq_id. Also sets the following attributes on the scenario: self._db_ctx, self.db, self.manager, and self.payload.
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

    async def when_dlq_entry_is_fetched_by_id(self):
        """
        Fetches the dead-letter-queue entry identified by self.dlq_id and stores it on self.entry.

        This step calls the retry manager to retrieve a single DLQ item by id and assigns the result to self.entry for later assertions in the scenario.
        """
        self.entry = await self.manager.get_dlq_entry(self.dlq_id)

    def then_entry_should_be_a_dlq_item(self):
        """
        Asserts that the fetched entry is a DLQItem.

        Raises:
            AssertionError: If self.entry is not an instance of DLQItem.
        """
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
        """
        Exit and close the test SQLite database context.

        Performs the asynchronous context manager exit on the stored database context to release resources and close connections.
        """
        await self._db_ctx.__aexit__(None, None, None)
