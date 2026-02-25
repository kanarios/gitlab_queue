"""Test scenario: get_latest_mr_pipeline returns None when no pipelines."""

from __future__ import annotations

import vedro
from scenarios.contexts.gitlab_client_factory import TEST_PROJECT_ID, created_test_client
from scenarios.transports import GitLabMockTransport


class Scenario(vedro.Scenario):
    subject = "get_latest_mr_pipeline returns None when no pipelines"

    def given_mock_gitlab_without_pipelines(self):
        self.transport = GitLabMockTransport()
        self.transport.register_get(
            f"/api/v4/projects/{TEST_PROJECT_ID}/merge_requests/42/pipelines",
            json_data=[],
        )
        self.client = created_test_client(transport=self.transport)

    async def when_get_latest_mr_pipeline_is_called(self):
        self.result = await self.client.get_latest_mr_pipeline(42)

    def then_result_should_be_none(self):
        assert self.result is None

    async def do_cleanup(self):
        await self.client.close()
