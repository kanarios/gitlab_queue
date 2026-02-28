"""Test scenario: 503 response raises GitLabServerError."""

from __future__ import annotations

import vedro

from gitlab_queue.clients.gitlab import (
    GitLabServerError,
)
from scenarios.contexts.gitlab_client_factory import TEST_PROJECT_ID, create_test_client
from scenarios.contexts.jj_gitlab_mock import mocked_gitlab_get_mr
from scenarios.schemas.status_code import ServiceUnavailableStatusSchema


class Scenario(vedro.Scenario):
    subject = "try to get mr when gitlab returns 503"

    async def given_mock_gitlab_returns_503(self):
        self._mock_ctx = mocked_gitlab_get_mr(
            TEST_PROJECT_ID,
            42,
            {"error": "Service Unavailable"},
            status=503,
        )
        await self._mock_ctx.__aenter__()
        self.client = create_test_client()

    async def when_get_mr_is_called(self):
        self.error = None
        try:
            await self.client.get_mr(42)
        except GitLabServerError as e:
            self.error = e

    def then_server_error_should_be_raised(self):
        assert self.error is not None
        assert isinstance(self.error, GitLabServerError)

    def and_status_code_should_be_503(self):
        assert self.error.status_code == ServiceUnavailableStatusSchema

    async def do_cleanup(self):
        await self.client.close()
        await self._mock_ctx.__aexit__(None, None, None)
