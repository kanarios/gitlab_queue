"""Test scenario: 409 response raises GitLabConflictError."""

from __future__ import annotations

import vedro
from scenarios.contexts.gitlab_client_factory import TEST_PROJECT_ID, create_test_client
from scenarios.contexts.jj_gitlab_mock import mocked_gitlab_get_mr
from scenarios.schemas.status_code import ConflictStatusSchema

from gitlab_queue.clients.gitlab import (
    GitLabConflictError,
)


class Scenario(vedro.Scenario):
    subject = "try to get mr when gitlab returns 409"

    async def given_mock_gitlab_returns_409(self):
        self._mock_ctx = mocked_gitlab_get_mr(
            TEST_PROJECT_ID,
            42,
            {"message": "409 Conflict"},
            status=409,
        )
        await self._mock_ctx.__aenter__()
        self.client = create_test_client()

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
        await self._mock_ctx.__aexit__(None, None, None)
