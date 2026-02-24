"""Test scenario: get_pipeline_status returns pipeline by ID."""

from __future__ import annotations

import vedro
from scenarios.contexts.gitlab_client_factory import TEST_PROJECT_ID, created_test_client
from scenarios.transports import GitLabMockTransport

from ._helpers import create_pipeline_response


class Scenario(vedro.Scenario):
    subject = "get_pipeline_status returns pipeline by ID"

    def given_mock_gitlab_with_pipeline(self):
        self.pipeline_data = create_pipeline_response(
            456,
            status="running",
            sha="running123",
            ref="main",
        )
        self.transport = GitLabMockTransport()
        self.transport.register_get(
            f"/api/v4/projects/{TEST_PROJECT_ID}/pipelines/456",
            json_data=self.pipeline_data,
        )
        self.client = created_test_client(transport=self.transport)

    async def when_get_pipeline_status_is_called(self):
        self.result = await self.client.get_pipeline_status(456)

    def then_pipeline_should_be_returned(self):
        assert self.result is not None
        assert self.result.id == 456

    def and_status_should_be_running(self):
        assert self.result.status == "running"

    def and_sha_should_match(self):
        assert self.result.sha == "running123"

    async def do_cleanup(self):
        if hasattr(self, "client"):
            await self.client.close()
