"""Test scenario: get_mr_conflicts uses old_path when new_path is missing."""

from __future__ import annotations

import vedro
from scenarios.contexts.gitlab_client_factory import TEST_PROJECT_ID, created_test_client
from scenarios.transports import GitLabMockTransport


class Scenario(vedro.Scenario):
    subject = "get_mr_conflicts uses old_path when new_path is missing"

    def given_mock_gitlab_with_old_path_only(self):
        self.conflicts_data = [
            {"old_path": "legacy.py"},  # No new_path
        ]
        self.transport = GitLabMockTransport()
        self.transport.register_get(
            f"/api/v4/projects/{TEST_PROJECT_ID}/merge_requests/42/conflicts",
            json_data=self.conflicts_data,
        )
        self.client = created_test_client(transport=self.transport)

    async def when_get_mr_conflicts_is_called(self):
        self.result = await self.client.get_mr_conflicts(42)

    def then_result_should_contain_old_path(self):
        assert self.result == ["legacy.py"]

    async def do_cleanup(self):
        if hasattr(self, "client"):
            await self.client.close()
