"""Test that get_events_ready_for_retry returns items that are due."""

from __future__ import annotations

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database

from gitlab_queue.models.retry import RetryQueueItem

from ._helpers import create_test_payload, create_test_retry_manager


class Scenario(vedro.Scenario):
    subject = "get events ready for retry returns due items"

    async def given_event_in_retry_queue(self):
        """
        Create a retry queue item in an initialized test database and attach test fixtures to the Scenario.
        
        Sets up an initialized test database context and stores it on `self._db_ctx`, obtains and stores the database handle on `self.db`, creates and stores a test retry manager on `self.manager` (configured with base_delay_seconds=0 and max_attempts=3), ensures the retry schema exists, creates and stores a test payload on `self.payload`, and enqueues a retry item with event_type "merge_request" and error "timeout error", storing the resulting item id on `self.retry_id` for later assertions and cleanup.
        """
        self._db_ctx = initialized_test_database()
        self.db = await self._db_ctx.__aenter__()
        self.manager = create_test_retry_manager(self.db, base_delay_seconds=0, max_attempts=3)
        await self.manager.ensure_schema()
        self.payload = create_test_payload()
        self.retry_id = await self.manager.add_to_retry_queue(
            event_type="merge_request",
            payload=self.payload,
            error="timeout error",
        )

    async def when_ready_events_are_fetched(self):
        """
        Fetches retry queue items that are due and saves them on the scenario.
        
        Sets self.ready_events to the list of RetryQueueItem objects returned by the retry manager's get_events_ready_for_retry().
        """
        self.ready_events = await self.manager.get_events_ready_for_retry()

    def then_one_item_should_be_returned(self):
        """
        Assert that exactly one event was returned by the ready events query.
        """
        assert len(self.ready_events) == 1

    def and_item_should_be_a_retry_queue_item(self):
        """
        Assert that the first ready event is a RetryQueueItem.
        
        Raises:
            AssertionError: If the first item in self.ready_events is not an instance of RetryQueueItem.
        """
        assert isinstance(self.ready_events[0], RetryQueueItem)

    def and_item_fields_should_match(self):
        """
        Assert that the first ready event's fields match the expected values stored during setup.
        
        Checks:
        - id equals the stored `retry_id`
        - `event_type` is "merge_request"
        - `payload` equals the stored payload
        - `attempt_count` is 0
        - `max_attempts` is 3
        - `last_error` is "timeout error"
        - `next_attempt_at` is not None
        - `created_at` is not None
        """
        item = self.ready_events[0]
        assert item.id == self.retry_id
        assert item.event_type == "merge_request"
        assert item.payload == self.payload
        assert item.attempt_count == 0
        assert item.max_attempts == 3
        assert item.last_error == "timeout error"
        assert item.next_attempt_at is not None
        assert item.created_at is not None

    async def do_cleanup(self):
        """
        Close the initialized test database context to clean up resources.
        
        Exits the asynchronous database context manager opened during setup, releasing connections and any associated temporary state.
        """
        await self._db_ctx.__aexit__(None, None, None)
