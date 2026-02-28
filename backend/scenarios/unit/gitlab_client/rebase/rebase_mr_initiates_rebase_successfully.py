"""Test scenario: rebase_mr initiates rebase successfully."""

from __future__ import annotations

import vedro

from scenarios.contexts.gitlab_client_factory import TEST_PROJECT_ID, created_test_client
from scenarios.transports import GitLabMockTransport


class Scenario(vedro.Scenario):
    subject = "rebase_mr initiates rebase successfully"

    def given_mock_gitlab_for_rebase(self):
        self.transport = GitLabMockTransport()
        self.transport.register_put(
            f"/api/v4/projects/{TEST_PROJECT_ID}/merge_requests/42/rebase",
            json_data={"rebase_in_progress": True},
        )
        self.client = created_test_client(transport=self.transport)

    async def when_rebase_mr_is_called(self):
        self.result = await self.client.rebase_mr(42)

    def then_result_should_be_true(self):
        assert self.result is True

    async def do_cleanup(self):
        await self.client.close()
