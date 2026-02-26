"""Test scenario: create_pipeline creates pipeline via API."""

from __future__ import annotations

import vedro

from scenarios.contexts.gitlab_client_factory import TEST_PROJECT_ID, created_test_client
from scenarios.transports import GitLabMockTransport

from ._helpers import create_pipeline_response


class Scenario(vedro.Scenario):
    subject = "create_pipeline creates pipeline via API"

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
            f"/api/v4/projects/{TEST_PROJECT_ID}/pipelines",
            json_data=self.pipeline_data,
        )
        self.client = created_test_client(transport=self.transport)

    async def when_create_pipeline_is_called(self):
        self.result = await self.client.create_pipeline(self.ref)

    def then_pipeline_should_be_returned(self):
        assert self.result is not None
        assert self.result.id == 789

    def and_status_should_be_pending(self):
        assert self.result.status == "pending"

    def and_sha_should_match(self):
        assert self.result.sha == "newsha123"

    def and_request_should_have_correct_ref(self):
        request_body = self.transport.get_request_json()
        assert request_body["ref"] == self.ref

    async def do_cleanup(self):
        await self.client.close()
