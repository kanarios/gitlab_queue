"""Test scenario: get_mr_conflicts returns empty list on API error."""

from __future__ import annotations

import vedro

from scenarios.contexts.gitlab_client_factory import TEST_PROJECT_ID, created_test_client
from scenarios.transports import GitLabMockTransport


class Scenario(vedro.Scenario):
    subject = "get_mr_conflicts returns empty list on API error"

    def given_mock_gitlab_returns_404(self):
        self.transport = GitLabMockTransport()
        self.transport.register_get(
            f"/api/v4/projects/{TEST_PROJECT_ID}/merge_requests/42/conflicts",
            json_data={"message": "Not Found"},
            status=404,
        )
        self.client = created_test_client(transport=self.transport)

    async def when_get_mr_conflicts_is_called(self):
        # Should not raise, returns empty list as fallback
        self.result = await self.client.get_mr_conflicts(42)

    def then_result_should_be_empty(self):
        assert self.result == []

    async def do_cleanup(self):
        await self.client.close()
