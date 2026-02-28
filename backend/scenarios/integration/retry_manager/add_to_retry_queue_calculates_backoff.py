"""Test that add_to_retry_queue calculates exponential backoff correctly."""

from __future__ import annotations

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database

from ._helpers import create_test_payload, create_test_retry_manager


class Scenario(vedro.Scenario):
    subject = "add to retry queue calculates backoff delay"

    async def given_retry_manager_with_30s_delay(self):
        """
        Prepare a retry manager configured with a 30-second base delay and attach it to the scenario using a test database.

        Sets up a test database context and stores the context on `self._db_ctx`, the opened database connection on `self.db`, and the configured retry manager on `self.manager`. Ensures the manager's schema exists. The retry manager is created with base_delay_seconds=30 and max_delay_seconds=300.
        """
        self._db_ctx = initialized_test_database()
        self.db = await self._db_ctx.__aenter__()
        self.manager = create_test_retry_manager(
            self.db,
            base_delay_seconds=30,
            max_delay_seconds=300,
        )
        await self.manager.ensure_schema()

    async def when_event_is_added(self):
        """
        Adds a retryable event to the retry queue with a 30-second base delay and stores the created retry record id.

        Calls the retry manager to enqueue an event of type "merge_request" with a test payload and error "server error", then assigns the returned retry identifier to self.retry_id for later assertions.
        """
        self.retry_id = await self.manager.add_to_retry_queue(
            event_type="merge_request",
            payload=create_test_payload(),
            error="server error",
        )

    async def then_event_should_not_be_ready_yet(self):
        """
        Asserts that no retryable events are currently ready for retry.

        Raises an AssertionError if any events are ready; the test expects the backoff delay (30 seconds) to keep the event in the future.
        """
        ready_events = await self.manager.get_events_ready_for_retry()
        assert len(ready_events) == 0, (
            f"Expected 0 ready events (backoff is 30s in the future), got {len(ready_events)}"
        )

    async def do_cleanup(self):
        """
        Release resources by exiting the asynchronous database context opened for the scenario.

        This invokes the context's asynchronous exit with no exception information to close connections and perform cleanup of test database resources.
        """
        await self._db_ctx.__aexit__(None, None, None)
