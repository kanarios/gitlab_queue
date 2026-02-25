"""Test that get_dlq_stats returns correct counts and breakdown."""

from __future__ import annotations

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database

from gitlab_queue.models.retry import DLQStats

from ._helpers import create_test_payload, create_test_retry_manager


class Scenario(vedro.Scenario):
    subject = "get dlq stats returns correct counts"

    async def given_dlq_entries_of_mixed_types(self):
        self._db_ctx = initialized_test_database()
        self.db = await self._db_ctx.__aenter__()
        self.manager = create_test_retry_manager(
            self.db,
            max_attempts=1,
            base_delay_seconds=0,
        )
        await self.manager.ensure_schema()

        # Add 2 merge_request DLQ entries
        for i in range(2):
            retry_id = await self.manager.add_to_retry_queue(
                event_type="merge_request",
                payload=create_test_payload("merge_request"),
                error=f"mr error {i}",
            )
            await self.manager.mark_retry_failed(retry_id, f"mr final error {i}")

        # Add 1 pipeline DLQ entry
        retry_id = await self.manager.add_to_retry_queue(
            event_type="pipeline",
            payload=create_test_payload("pipeline"),
            error="pipeline error",
        )
        await self.manager.mark_retry_failed(retry_id, "pipeline final error")

    async def when_dlq_stats_are_fetched(self):
        self.stats = await self.manager.get_dlq_stats()

    def then_stats_should_be_dlq_stats_instance(self):
        assert isinstance(self.stats, DLQStats)

    def and_total_count_should_be_3(self):
        assert self.stats.total_count == 3

    def and_by_event_type_should_have_correct_counts(self):
        assert self.stats.by_event_type.get("merge_request") == 2
        assert self.stats.by_event_type.get("pipeline") == 1

    def and_oldest_entry_should_be_set(self):
        assert self.stats.oldest_entry is not None

    async def do_cleanup(self):
        await self._db_ctx.__aexit__(None, None, None)
