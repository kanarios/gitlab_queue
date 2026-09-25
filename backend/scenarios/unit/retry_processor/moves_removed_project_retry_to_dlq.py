"""Test that ready retries for removed projects are sent to the DLQ."""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, cast

import vedro

from scenarios.fakes import FakeRetryManager

from ._helpers import create_test_retry_item, create_test_retry_processor

if TYPE_CHECKING:
    from gitlab_queue.core.project_components import ProjectComponents


class Scenario(vedro.Scenario):
    subject = "retry processor moves removed-project retries to the DLQ"

    def given_processor_with_two_configured_projects_and_a_removed_project_retry(self):
        self.removed_project_item = replace(
            create_test_retry_item(item_id=7, event_type="unknown", payload={}),
            project_id=303,
        )
        self.retry_manager = FakeRetryManager(_ready_events=[self.removed_project_item])
        project_components = {
            101: cast("ProjectComponents", object()),
            202: cast("ProjectComponents", object()),
        }
        self.processor = create_test_retry_processor(
            retry_manager=self.retry_manager,
            project_components=project_components,
        )

    async def when_retry_iteration_runs(self):
        await self.processor._process_iteration()

    def then_each_configured_project_gets_its_own_batch_query(self):
        assert [call["project_id"] for call in self.retry_manager.get_events_calls[:2]] == [101, 202]
        assert all(call["limit"] == 10 for call in self.retry_manager.get_events_calls[:2])

    def and_unconfigured_rows_are_queried_separately(self):
        assert self.retry_manager.get_events_calls[2] == {
            "limit": 10,
            "project_id": None,
            "excluded_project_ids": (101, 202),
        }

    def and_the_removed_project_item_is_moved_to_dlq_without_replay(self):
        assert self.retry_manager.dlq_calls == [
            {
                "item_id": self.removed_project_item.id,
                "error": "Project is no longer configured; automatic retry was stopped",
                "project_id": 303,
            }
        ]
        assert self.retry_manager.success_calls == []
        assert self.retry_manager.failed_calls == []
