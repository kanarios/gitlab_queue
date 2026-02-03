"""Test scenario: cancel_pipeline returns cancelled pipeline."""

from __future__ import annotations

import vedro
from scenarios.contexts.gitlab_client_factory import TEST_PROJECT_ID, created_test_client
from scenarios.transports import GitLabMockTransport
from scenarios.transports.responses import pipeline_response


class Scenario(vedro.Scenario):
    subject = "cancel_pipeline returns cancelled pipeline"

    def given_mock_gitlab_with_pipeline_cancel(self):
        self.pipeline_data = pipeline_response(
            100,
            status="canceled",
            sha="abc123def456",
            ref="main",
        )
        self.transport = GitLabMockTransport()
        self.transport.register_post(
            f"/api/v4/projects/{TEST_PROJECT_ID}/pipelines/100/cancel",
            json_data=self.pipeline_data,
        )
        self.client = created_test_client(transport=self.transport)

    async def when_cancel_pipeline_is_called(self):
        self.result = await self.client.cancel_pipeline(100)

    def then_pipeline_should_be_returned(self):
        assert self.result is not None
        assert self.result.id == 100

    def and_status_should_be_canceled(self):
        assert self.result.status == "canceled"

    def and_sha_should_match(self):
        assert self.result.sha == "abc123def456"

    async def do_cleanup(self):
        await self.client.close()
