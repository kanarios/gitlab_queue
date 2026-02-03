"""Test that get_events_ready_for_retry returns items that are due."""

from __future__ import annotations

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database

from gitlab_queue.models.retry import RetryQueueItem

from ._helpers import create_test_payload, create_test_retry_manager


class Scenario(vedro.Scenario):
    subject = "get events ready for retry returns due items"

    async def given_event_in_retry_queue(self):
        self._db_ctx = initialized_test_database()
        self.db = await self._db_ctx.__aenter__()
        self.manager = create_test_retry_manager(self.db, base_delay_seconds=0)
        await self.manager.ensure_schema()
        self.payload = create_test_payload()
        self.retry_id = await self.manager.add_to_retry_queue(
            event_type="merge_request",
            payload=self.payload,
            error="timeout error",
        )

    async def when_ready_events_are_fetched(self):
        self.ready_events = await self.manager.get_events_ready_for_retry()

    def then_one_item_should_be_returned(self):
        assert len(self.ready_events) == 1, f"Expected 1 ready event, got {len(self.ready_events)}"

    def and_item_should_be_a_retry_queue_item(self):
        assert isinstance(self.ready_events[0], RetryQueueItem)

    def and_item_fields_should_match(self):
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
        await self._db_ctx.__aexit__(None, None, None)
