"""Test that excluded project retries can be moved directly to the DLQ."""

from __future__ import annotations

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database

from ._helpers import create_test_payload, create_test_retry_manager


class Scenario(vedro.Scenario):
    subject = "removed-project retries move to DLQ without counting another attempt"

    async def given_retry_items_for_configured_and_removed_projects(self):
        self._db_ctx = initialized_test_database()
        self.db = await self._db_ctx.__aenter__()
        self.manager = create_test_retry_manager(self.db, base_delay_seconds=0)
        await self.manager.ensure_schema()
        self.configured_first_id = await self.manager.add_to_retry_queue(
            "merge_request", create_test_payload(), "configured first", project_id=101
        )
        self.configured_second_id = await self.manager.add_to_retry_queue(
            "merge_request", create_test_payload(), "configured second", project_id=202
        )
        self.removed_project_id = await self.manager.add_to_retry_queue(
            "merge_request", create_test_payload(), "removed project", project_id=303
        )

    async def when_removed_project_items_are_selected_and_moved_to_dlq(self):
        ready = await self.manager.get_events_ready_for_retry(
            limit=1,
            excluded_project_ids=(101, 202),
        )
        self.ready_ids = [item.id for item in ready]
        await self.manager.move_retry_to_dlq(
            self.removed_project_id,
            "Project is no longer configured; automatic retry was stopped",
            project_id=303,
        )
        self.dlq_entries = await self.manager.get_dlq_entries(project_id=303)
        self.remaining_removed_project_items = await self.manager.get_events_ready_for_retry(project_id=303)

    def then_exclusions_are_applied_before_the_limit(self):
        assert self.ready_ids == [self.removed_project_id]
        assert self.configured_first_id != self.configured_second_id

    def and_removed_project_retry_is_no_longer_automatically_ready(self):
        assert self.remaining_removed_project_items == []

    def and_dlq_retains_the_original_attempt_count(self):
        assert len(self.dlq_entries) == 1
        assert self.dlq_entries[0].project_id == 303
        assert self.dlq_entries[0].attempt_count == 0

    async def do_cleanup(self):
        await self._db_ctx.__aexit__(None, None, None)
