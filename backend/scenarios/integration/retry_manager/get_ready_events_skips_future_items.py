"""Test that get_events_ready_for_retry skips items scheduled in the future."""

from __future__ import annotations

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database

from ._helpers import create_test_payload, create_test_retry_manager


class Scenario(vedro.Scenario):
    subject = "get events ready for retry skips future items"

    async def given_event_with_far_future_backoff(self):
        self._db_ctx = initialized_test_database()
        self.db = await self._db_ctx.__aenter__()
        self.manager = create_test_retry_manager(
            self.db,
            base_delay_seconds=3600,
            max_delay_seconds=7200,
        )
        await self.manager.ensure_schema()
        await self.manager.add_to_retry_queue(
            event_type="merge_request",
            payload=create_test_payload(),
            error="some error",
        )

    async def when_ready_events_are_fetched(self):
        self.ready_events = await self.manager.get_events_ready_for_retry()

    def then_no_events_should_be_returned(self):
        assert len(self.ready_events) == 0

    async def do_cleanup(self):
        await self._db_ctx.__aexit__(None, None, None)
