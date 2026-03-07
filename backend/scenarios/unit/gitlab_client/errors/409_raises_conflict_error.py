"""Test scenario: 409 response raises GitLabConflictError."""

from __future__ import annotations

import vedro

from gitlab_queue.clients.gitlab import (
    GitLabConflictError,
)
from scenarios.contexts.gitlab_client_factory import TEST_PROJECT_ID, created_test_client
from scenarios.schemas.status_code import ConflictStatusSchema
from scenarios.transports import GitLabMockTransport


class Scenario(vedro.Scenario):
    subject = "try to get mr when gitlab returns 409"

    def given_mock_gitlab_returns_409(self):
        self.transport = GitLabMockTransport()
        self.transport.register_get(
            f"/api/v4/projects/{TEST_PROJECT_ID}/merge_requests/42",
            status=409,
            json_data={"message": "409 Conflict"},
        )
        self.client = created_test_client(transport=self.transport)

    async def when_get_mr_is_called(self):
        self.error = None
        try:
            await self.client.get_mr(42)
        except GitLabConflictError as e:
            self.error = e

    def then_conflict_error_should_be_raised(self):
        assert self.error is not None
        assert isinstance(self.error, GitLabConflictError)

    def and_status_code_should_be_409(self):
        assert self.error.status_code == ConflictStatusSchema

    async def do_cleanup(self):
        await self.client.close()
