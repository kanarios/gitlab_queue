"""Test that delete_dlq_entry removes the item from the DLQ."""

from __future__ import annotations

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database

from ._helpers import create_test_payload, create_test_retry_manager


class Scenario(vedro.Scenario):
    subject = "delete dlq entry removes item from dlq"

    async def given_dlq_entry(self):
        """
        Prepare a dead-letter queue (DLQ) entry in the test database and record its id on the scenario.
        
        Initializes a test SQLite database context, creates a RetryManager configured for a single attempt with no delay, ensures the required schema, adds a retry entry (event_type "merge_request") and marks it as failed, then retrieves the DLQ and saves the first entry's id to self.dlq_id.
        """
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
        """
        Delete the DLQ entry identified by self.dlq_id and store the outcome.
        
        Sets `self.deleted` to `True` if the manager successfully deleted the DLQ entry, `False` otherwise.
        """
        self.deleted = await self.manager.delete_dlq_entry(self.dlq_id)

    def then_delete_should_return_true(self):
        assert self.deleted is True

    async def and_dlq_should_be_empty(self):
        """
        Asserts that the dead-letter queue contains no entries.
        
        Raises an AssertionError if any DLQ entries are present.
        """
        entries = await self.manager.get_dlq_entries()
        assert len(entries) == 0

    async def do_cleanup(self):
        """
        Close the test database context used by the scenario and release associated resources.
        """
        await self._db_ctx.__aexit__(None, None, None)
