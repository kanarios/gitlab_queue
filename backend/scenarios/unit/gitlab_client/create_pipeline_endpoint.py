"""Test scenario: create_pipeline uses correct singular endpoint /pipeline."""

from __future__ import annotations

import vedro

from scenarios.contexts.gitlab_client_factory import TEST_PROJECT_ID, created_test_client
from scenarios.transports import GitLabMockTransport

from .pipelines._helpers import create_pipeline_response


class Scenario(vedro.Scenario):
    subject = "create_pipeline uses correct singular endpoint /pipeline"

    def given_mock_gitlab(self):
        self.ref = "feature-branch"
        self.pipeline_data = create_pipeline_response(
            789,
            status="pending",
            sha="newsha123",
            ref=self.ref,
        )
        self.transport = GitLabMockTransport()
        self.transport.register_post(
            f"/api/v4/projects/{TEST_PROJECT_ID}/pipeline",
            json_data=self.pipeline_data,
        )
        self.client = created_test_client(transport=self.transport)

    async def when_create_pipeline_is_called(self):
        self.result = await self.client.create_pipeline(self.ref)

    def then_pipeline_should_be_returned(self):
        assert self.result is not None
        assert self.result.id == 789

    def then_request_used_singular_pipeline_endpoint(self):
        self.transport.assert_called_with_path(f"/api/v4/projects/{TEST_PROJECT_ID}/pipeline")

    async def do_cleanup(self):
        await self.client.close()
