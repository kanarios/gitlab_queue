"""Test scenario: 404 response raises GitLabNotFoundError."""

from __future__ import annotations

import vedro

from gitlab_queue.clients.gitlab import (
    GitLabAPIError,
    GitLabNotFoundError,
)
from scenarios.contexts.gitlab_client_factory import TEST_PROJECT_ID, created_test_client
from scenarios.schemas.status_code import NotFoundStatusSchema
from scenarios.transports import GitLabMockTransport


class Scenario(vedro.Scenario):
    subject = "try to get mr when gitlab returns 404"

    def given_mock_gitlab_returns_404(self):
        self.transport = GitLabMockTransport()
        self.transport.register_get(
            f"/api/v4/projects/{TEST_PROJECT_ID}/merge_requests/999",
            status=404,
            json_data={"message": "404 Project Not Found"},
        )
        self.client = created_test_client(transport=self.transport)

    async def when_get_mr_is_called(self):
        self.error = None
        try:
            await self.client.get_mr(999)
        except GitLabNotFoundError as e:
            self.error = e

    def then_not_found_error_should_be_raised(self):
        assert self.error is not None
        assert isinstance(self.error, GitLabNotFoundError)

    def and_status_code_should_be_404(self):
        assert self.error.status_code == NotFoundStatusSchema

    def and_error_should_be_api_error_subclass(self):
        assert isinstance(self.error, GitLabAPIError)

    async def do_cleanup(self):
        await self.client.close()
