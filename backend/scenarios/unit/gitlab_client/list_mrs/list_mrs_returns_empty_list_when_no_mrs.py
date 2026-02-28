"""Test scenario: list_mrs_with_label returns empty list when no MRs."""

from __future__ import annotations

import vedro

from scenarios.contexts.gitlab_client_factory import TEST_PROJECT_ID, created_test_client
from scenarios.transports import GitLabMockTransport


class Scenario(vedro.Scenario):
    subject = "list_mrs_with_label returns empty list when no MRs"

    def given_mock_gitlab_with_no_mrs(self):
        self.transport = GitLabMockTransport()
        self.transport.register_get(
            f"/api/v4/projects/{TEST_PROJECT_ID}/merge_requests",
            json_data=[],
        )
        self.client = created_test_client(transport=self.transport)

    async def when_list_mrs_is_called(self):
        self.result = await self.client.list_mrs_with_label("merge_queue")

    def then_result_should_be_empty_list(self):
        assert self.result == []

    async def do_cleanup(self):
        await self.client.close()
