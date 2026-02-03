"""Test that get_dlq_entries returns paginated results."""

from __future__ import annotations

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database

from ._helpers import create_test_payload, create_test_retry_manager


class Scenario(vedro.Scenario):
    subject = "get dlq entries returns paginated results"

    async def given_three_dlq_entries(self):
        self._db_ctx = initialized_test_database()
        self.db = await self._db_ctx.__aenter__()
        self.manager = create_test_retry_manager(
            self.db,
            max_attempts=1,
            base_delay_seconds=0,
        )
        await self.manager.ensure_schema()

        for i in range(3):
            retry_id = await self.manager.add_to_retry_queue(
                event_type="merge_request",
                payload=create_test_payload(),
                error=f"error {i}",
            )
            await self.manager.mark_retry_failed(retry_id, f"final error {i}")

    async def when_dlq_entries_fetched_with_limit_2(self):
        self.entries = await self.manager.get_dlq_entries(limit=2)

    def then_two_entries_should_be_returned(self):
        assert len(self.entries) == 2, f"Expected 2 DLQ entries (limit=2), got {len(self.entries)}"

    async def and_all_three_entries_should_exist(self):
        all_entries = await self.manager.get_dlq_entries(limit=50)
        assert len(all_entries) == 3, f"Expected 3 total DLQ entries, got {len(all_entries)}"

    async def do_cleanup(self):
        await self._db_ctx.__aexit__(None, None, None)
