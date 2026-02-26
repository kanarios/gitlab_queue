"""Test scenario: get_latest_mr_pipeline returns first (newest) pipeline."""

from __future__ import annotations

import vedro

from scenarios.contexts.gitlab_client_factory import TEST_PROJECT_ID, created_test_client
from scenarios.transports import GitLabMockTransport

from ._helpers import create_pipeline_response


class Scenario(vedro.Scenario):
    subject = "get_latest_mr_pipeline returns first (newest) pipeline"

    def given_mock_gitlab_with_multiple_pipelines(self):
        self.pipelines_data = [
            create_pipeline_response(100, status="success"),
            create_pipeline_response(99, status="failed"),
        ]
        self.transport = GitLabMockTransport()
        self.transport.register_get(
            f"/api/v4/projects/{TEST_PROJECT_ID}/merge_requests/42/pipelines",
            json_data=self.pipelines_data,
        )
        self.client = created_test_client(transport=self.transport)

    async def when_get_latest_mr_pipeline_is_called(self):
        self.result = await self.client.get_latest_mr_pipeline(42)

    def then_result_should_be_first_pipeline(self):
        assert self.result is not None
        assert self.result.id == 100

    def and_status_should_be_success(self):
        assert self.result.status == "success"

    async def do_cleanup(self):
        await self.client.close()
