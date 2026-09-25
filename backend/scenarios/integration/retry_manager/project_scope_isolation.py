"""Retry and DLQ queries must never cross project boundaries."""

from __future__ import annotations

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database

from ._helpers import create_test_payload, create_test_retry_manager


class Scenario(vedro.Scenario):
    subject = "retry and dlq records are isolated by project"

    async def given_records_for_two_projects(self):
        self._db_ctx = initialized_test_database()
        self.db = await self._db_ctx.__aenter__()
        self.manager = create_test_retry_manager(self.db, base_delay_seconds=0, max_attempts=1)
        await self.manager.ensure_schema()

        self.first_id = await self.manager.add_to_retry_queue(
            "merge_request", create_test_payload(), "first", project_id=101
        )
        self.second_id = await self.manager.add_to_retry_queue(
            "merge_request", create_test_payload(), "second", project_id=202
        )

    async def when_project_records_are_queried(self):
        self.first_ready = await self.manager.get_events_ready_for_retry(project_id=101)
        self.second_ready = await self.manager.get_events_ready_for_retry(project_id=202)
        await self.manager.mark_retry_failed(self.first_id, "failed", project_id=101)
        self.first_dlq = await self.manager.get_dlq_entries(project_id=101)
        self.second_dlq = await self.manager.get_dlq_entries(project_id=202)

    def then_each_retry_query_contains_only_its_project(self):
        assert [item.id for item in self.first_ready] == [self.first_id]
        assert [item.project_id for item in self.first_ready] == [101]
        assert [item.id for item in self.second_ready] == [self.second_id]
        assert [item.project_id for item in self.second_ready] == [202]

    def and_dlq_queries_are_isolated(self):
        assert [item.project_id for item in self.first_dlq] == [101]
        assert self.second_dlq == []

    async def do_cleanup(self):
        await self._db_ctx.__aexit__(None, None, None)
