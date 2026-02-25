"""Test scenario: rebase_mr raises GitLabConflictError on 409."""

from __future__ import annotations

import vedro
from scenarios.contexts.gitlab_client_factory import TEST_PROJECT_ID, created_test_client
from scenarios.schemas.status_code import ConflictStatusSchema
from scenarios.transports import GitLabMockTransport

from gitlab_queue.clients.gitlab import GitLabConflictError


class Scenario(vedro.Scenario):
    subject = "try to rebase mr when gitlab returns 409"

    def given_mock_gitlab_returns_conflict(self):
        self.transport = GitLabMockTransport()
        self.transport.register_put(
            f"/api/v4/projects/{TEST_PROJECT_ID}/merge_requests/42/rebase",
            json_data={"message": "Rebase already in progress"},
            status=409,
        )
        self.client = created_test_client(transport=self.transport)

    async def when_rebase_mr_is_called(self):
        self.error = None
        try:
            await self.client.rebase_mr(42)
        except GitLabConflictError as e:
            self.error = e

    def then_error_should_be_raised(self):
        assert self.error is not None

    def and_error_should_be_conflict_error(self):
        assert isinstance(self.error, GitLabConflictError)

    def and_status_code_should_be_409(self):
        assert self.error.status_code == ConflictStatusSchema

    async def do_cleanup(self):
        await self.client.close()
