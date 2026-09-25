"""Test that FakeRetryManager applies the project filter before the limit."""

from __future__ import annotations

from dataclasses import replace

import vedro

from scenarios.fakes import FakeRetryManager

from ._helpers import create_test_retry_item


class Scenario(vedro.Scenario):
    subject = "FakeRetryManager filters by project before applying the limit"

    def given_retry_items_for_multiple_projects(self):
        self.other_project_item = replace(create_test_retry_item(item_id=1), project_id=202)
        self.requested_project_item = replace(create_test_retry_item(item_id=2), project_id=101)
        self.retry_manager = FakeRetryManager(_ready_events=[self.other_project_item, self.requested_project_item])

    async def when_ready_items_are_requested_for_one_project_with_limit_one(self):
        self.items = await self.retry_manager.get_events_ready_for_retry(limit=1, project_id=101)

    def then_the_matching_project_item_is_returned(self):
        assert self.items == [self.requested_project_item]
