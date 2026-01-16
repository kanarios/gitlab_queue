"""Test scenario: rebase_mr raises GitLabConflictError on 409."""

from __future__ import annotations

import vedro
from scenarios.contexts.gitlab_client_factory import TEST_PROJECT_ID, create_test_client
from scenarios.contexts.jj_gitlab_mock import mocked_gitlab_rebase
from scenarios.schemas.status_code import ConflictStatusSchema

from gitlab_queue.clients.gitlab import GitLabConflictError


class Scenario(vedro.Scenario):
    subject = "try to rebase mr when gitlab returns 409"

    async def given_mock_gitlab_returns_conflict(self):
        self._mock_ctx = mocked_gitlab_rebase(TEST_PROJECT_ID, 42, success=False)
        await self._mock_ctx.__aenter__()
        self.client = create_test_client()

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
        await self._mock_ctx.__aexit__(None, None, None)
