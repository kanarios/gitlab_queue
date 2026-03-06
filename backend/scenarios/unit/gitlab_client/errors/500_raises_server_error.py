"""Test scenario: 500 response raises GitLabServerError."""

from __future__ import annotations

import vedro

from gitlab_queue.clients.gitlab import (
    GitLabServerError,
)
from scenarios.contexts.gitlab_client_factory import TEST_PROJECT_ID, created_test_client
from scenarios.schemas.status_code import InternalServerErrorStatusSchema
from scenarios.transports import GitLabMockTransport


class Scenario(vedro.Scenario):
    subject = "try to get mr when gitlab returns 500"

    def given_mock_gitlab_returns_500(self):
        self.transport = GitLabMockTransport()
        self.transport.register_get(
            f"/api/v4/projects/{TEST_PROJECT_ID}/merge_requests/42",
            status=500,
            json_data={"error": "Internal Server Error"},
        )
        self.client = created_test_client(transport=self.transport)

    async def when_get_mr_is_called(self):
        self.error = None
        try:
            await self.client.get_mr(42)
        except GitLabServerError as e:
            self.error = e

    def then_server_error_should_be_raised(self):
        assert self.error is not None
        assert isinstance(self.error, GitLabServerError)

    def and_status_code_should_be_500(self):
        assert self.error.status_code == InternalServerErrorStatusSchema

    async def do_cleanup(self):
        await self.client.close()
