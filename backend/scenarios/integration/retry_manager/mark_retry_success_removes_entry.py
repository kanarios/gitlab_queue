"""Test that mark_retry_success removes the entry from the queue."""

from __future__ import annotations

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database

from ._helpers import create_test_payload, create_test_retry_manager


class Scenario(vedro.Scenario):
    subject = "mark retry success removes entry from queue"

    async def given_event_in_retry_queue(self):
        """
        Populate the test retry queue with a single entry and prepare the retry manager.

        Sets up a test database context and binds a test retry manager (with base_delay_seconds=0),
        ensures the retry schema exists, and adds one retry entry with event_type "merge_request",
        a test payload, and error "transient error". Stores the database context, database handle,
        manager, and the created retry entry id on the instance as self._db_ctx, self.db, self.manager,
        and self.retry_id respectively.
        """
        self._db_ctx = initialized_test_database()
        self.db = await self._db_ctx.__aenter__()
        self.manager = create_test_retry_manager(self.db, base_delay_seconds=0)
        await self.manager.ensure_schema()
        self.retry_id = await self.manager.add_to_retry_queue(
            event_type="merge_request",
            payload=create_test_payload(),
            error="transient error",
        )

    async def when_retry_is_marked_successful(self):
        """
        Mark the previously queued retry entry as successful.

        Invokes the retry manager to mark the retry identified by self.retry_id as successful so it is removed from the retry queue.
        """
        await self.manager.mark_retry_success(self.retry_id)

    async def then_queue_should_be_empty(self):
        """
        Assert that no events are ready for retry.

        Raises:
            AssertionError: If one or more retryable events remain in the queue.
        """
        ready_events = await self.manager.get_events_ready_for_retry()
        assert len(ready_events) == 0

    async def do_cleanup(self):
        """
        Exit the asynchronous test database context used by the scenario.

        Performs cleanup by closing the database context acquired in setup, ensuring resources are released.
        """
        await self._db_ctx.__aexit__(None, None, None)
