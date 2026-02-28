"""Test that get_events_ready_for_retry skips items scheduled in the future."""

from __future__ import annotations

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database

from ._helpers import create_test_payload, create_test_retry_manager


class Scenario(vedro.Scenario):
    subject = "get events ready for retry skips future items"

    async def given_event_with_far_future_backoff(self):
        """
        Prepare test state by initializing a test database and retry manager, and inserting a retry queue item scheduled with a far-future backoff so it will not be ready for retry.

        This sets up:
        - an initialized test database context and connection,
        - a retry manager configured with large base and max delays,
        - one retry entry for event_type "merge_request" with a test payload and error.
        """
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
        """
        Fetches events that are ready for retry from the manager and stores them in self.ready_events.
        """
        self.ready_events = await self.manager.get_events_ready_for_retry()

    def then_no_events_should_be_returned(self):
        """
        Assert that no retry events were returned by the previous retrieval step.

        This verifies that the list of ready events is empty (length equals 0), ensuring future-scheduled items were not included.
        """
        assert len(self.ready_events) == 0

    async def do_cleanup(self):
        """
        Exit the test database context used by the scenario.

        Closes the asynchronous database context manager created for the test, releasing any resources held by the test database.
        """
        await self._db_ctx.__aexit__(None, None, None)
