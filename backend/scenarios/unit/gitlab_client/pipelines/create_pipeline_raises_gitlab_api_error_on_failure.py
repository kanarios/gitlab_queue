"""Test scenario: create_pipeline raises GitLabAPIError on failure."""

from __future__ import annotations

import vedro
from scenarios.contexts.gitlab_client_factory import TEST_PROJECT_ID, created_test_client
from scenarios.transports import GitLabMockTransport

from gitlab_queue.clients.gitlab import GitLabAPIError


class Scenario(vedro.Scenario):
    subject = "create_pipeline raises GitLabAPIError on failure"

    def given_mock_gitlab_returning_error(self):
        self.ref = "feature-branch"
        self.transport = GitLabMockTransport()
        self.transport.register_post(
            f"/api/v4/projects/{TEST_PROJECT_ID}/pipelines",
            status=400,
            json_data={"message": "No stages/jobs for this pipeline"},
        )
        self.client = created_test_client(transport=self.transport)

    async def when_create_pipeline_is_called(self):
        try:
            await self.client.create_pipeline(self.ref)
            self.error = None
        except GitLabAPIError as e:
            self.error = e

    def then_gitlab_api_error_should_be_raised(self):
        assert self.error is not None
        assert isinstance(self.error, GitLabAPIError)

    def and_error_should_have_correct_status_code(self):
        assert self.error.status_code == 400

    async def do_cleanup(self):
        await self.client.close()
