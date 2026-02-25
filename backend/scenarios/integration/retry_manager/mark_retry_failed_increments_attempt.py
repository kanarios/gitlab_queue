"""Test that mark_retry_failed increments attempt count and keeps item in queue."""

from __future__ import annotations

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database

from ._helpers import create_test_payload, create_test_retry_manager


class Scenario(vedro.Scenario):
    subject = "mark retry failed increments attempt count"

    async def given_event_in_retry_queue(self):
        """
        Prepare test state by creating an in-memory test database and a retry manager, ensuring the retry schema exists, and adding a retry event to the queue.
        
        The database context, active DB connection, retry manager, and the created retry item's ID are stored on `self` as `_db_ctx`, `db`, `manager`, and `retry_id` respectively. The retry manager is configured with max_attempts=3 and base_delay_seconds=0, and the enqueued event uses event_type "merge_request" with a test payload and an initial error.
        """
        self._db_ctx = initialized_test_database()
        self.db = await self._db_ctx.__aenter__()
        self.manager = create_test_retry_manager(
            self.db,
            max_attempts=3,
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
        Marks the queued retry identified by self.retry_id as failed and records whether it was moved to the dead-letter queue.
        
        Sets self.moved_to_dlq to `True` if the item was moved to the DLQ, `False` otherwise. The failure is recorded with the error message "error on attempt 1".
        """
        self.moved_to_dlq = await self.manager.mark_retry_failed(
            self.retry_id,
            "error on attempt 1",
        )

    def then_should_not_be_moved_to_dlq(self):
        """
        Asserts that the retry item was not moved to the dead-letter queue.
        
        Raises an AssertionError if the item was moved to the DLQ.
        """
        assert self.moved_to_dlq is False

    async def and_item_should_still_be_in_queue_with_incremented_attempt(self):
        # Use a new manager with base_delay_seconds=0 to read the updated item
        # because the backoff may have pushed next_attempt_at into the future
        """
        Verify that a retry item remains in the retry queue with an incremented attempt count and updated last error.
        
        Creates a new retry manager reader (with zero base delay to avoid backoff timing) to fetch ready-for-retry events, then asserts exactly one event is returned, its attempt_count is 1, and its last_error equals "error on attempt 1".
        """
        reader = create_test_retry_manager(self.db, base_delay_seconds=0)
        ready_events = await reader.get_events_ready_for_retry()
        assert len(ready_events) == 1
        item = ready_events[0]
        assert item.attempt_count == 1
        assert item.last_error == "error on attempt 1"

    async def do_cleanup(self):
        """
        Close and release the initialized test database context used by the scenario.
        
        This ensures the in-memory database and its resources are properly cleaned up after the test.
        """
        await self._db_ctx.__aexit__(None, None, None)
