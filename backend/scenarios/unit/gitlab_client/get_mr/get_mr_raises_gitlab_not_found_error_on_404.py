"""Test scenario: get_mr raises GitLabNotFoundError on 404."""

from __future__ import annotations

import vedro
from scenarios.contexts.gitlab_client_factory import TEST_PROJECT_ID, create_test_client
from scenarios.contexts.jj_gitlab_mock import mocked_gitlab_get_mr
from scenarios.schemas.status_code import NotFoundStatusSchema

from gitlab_queue.clients.gitlab import GitLabNotFoundError


class Scenario(vedro.Scenario):
    subject = "try to get mr when mr not found"

    async def given_mock_gitlab_returns_404(self):
        self.mr_data = {"message": "404 Not Found"}
        self._mock_ctx = mocked_gitlab_get_mr(TEST_PROJECT_ID, 999, self.mr_data, status=404)
        await self._mock_ctx.__aenter__()
        self.client = create_test_client()

    async def when_get_mr_is_called_for_nonexistent_mr(self):
        self.error = None
        try:
            await self.client.get_mr(999)
        except GitLabNotFoundError as e:
            self.error = e

    def then_error_should_be_raised(self):
        assert self.error is not None

    def and_error_should_be_not_found(self):
        assert isinstance(self.error, GitLabNotFoundError)

    def and_status_code_should_be_404(self):
        assert self.error.status_code == NotFoundStatusSchema

    async def do_cleanup(self):
        await self.client.close()
        await self._mock_ctx.__aexit__(None, None, None)
