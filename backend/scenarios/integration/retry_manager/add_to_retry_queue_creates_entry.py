"""Test that add_to_retry_queue creates an entry and returns a valid id."""

from __future__ import annotations

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database

from ._helpers import create_test_payload, create_test_retry_manager


class Scenario(vedro.Scenario):
    subject = "add to retry queue creates entry with valid id"

    async def given_retry_manager(self):
        """
        Set up a test SQLite database context and initialize a retry manager for the scenario.

        This prepares and stores the asynchronous database context, the database connection, and a retry manager configured with zero base delay, and ensures the manager's database schema exists for subsequent test steps.
        """
        self._db_ctx = initialized_test_database()
        self.db = await self._db_ctx.__aenter__()
        self.manager = create_test_retry_manager(self.db, base_delay_seconds=0)
        await self.manager.ensure_schema()

    async def when_event_is_added_to_retry_queue(self):
        """
        Adds a test "merge_request" event to the retry queue and records the created payload and retry entry id on the instance.

        After execution, self.payload contains the test payload and self.retry_id contains the id returned by add_to_retry_queue.
        """
        self.payload = create_test_payload()
        self.retry_id = await self.manager.add_to_retry_queue(
            event_type="merge_request",
            payload=self.payload,
            error="connection timeout",
        )

    def then_retry_id_should_be_positive(self):
        """
        Assert that the stored retry_id is greater than zero.

        Raises:
            AssertionError: If `retry_id` is not greater than zero.
        """
        assert self.retry_id > 0, f"Expected retry_id > 0, got {self.retry_id}"

    async def and_entry_should_be_retrievable(self):
        """
        Verify that the previously added retry entry can be retrieved and has the expected fields.

        Asserts exactly one event is ready for retry, and that the event's id, event_type, payload, attempt_count, and last_error match the values produced when the event was added.
        """
        ready_events = await self.manager.get_events_ready_for_retry()
        assert len(ready_events) == 1, f"Expected 1 ready event, got {len(ready_events)}"
        item = ready_events[0]
        assert item.id == self.retry_id
        assert item.event_type == "merge_request"
        assert item.payload == self.payload
        assert item.attempt_count == 0
        assert item.last_error == "connection timeout"

    async def do_cleanup(self):
        """
        Exit and clean up the test database context used by the scenario.

        Ensures the scenario's asynchronous database context is exited and any associated resources are released.
        """
        await self._db_ctx.__aexit__(None, None, None)
