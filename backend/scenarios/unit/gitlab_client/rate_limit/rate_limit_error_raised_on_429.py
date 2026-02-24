"""Test scenario: 429 response raises GitLabRateLimitError."""

from __future__ import annotations

import vedro
from scenarios.contexts.gitlab_client_factory import TEST_PROJECT_ID, created_test_client
from scenarios.transports import GitLabMockTransport
from scenarios.transports.responses import rate_limit_response

from gitlab_queue.clients.gitlab import GitLabRateLimitError


class Scenario(vedro.Scenario):
    subject = "429 response raises GitLabRateLimitError"

    def given_mock_gitlab_returns_429(self):
        self.transport = GitLabMockTransport()
        self.transport.register_get(
            f"/api/v4/projects/{TEST_PROJECT_ID}/merge_requests/42",
            status=429,
            json_data=rate_limit_response(),
            headers={
                "Retry-After": "60",
                "RateLimit-Limit": "100",
                "RateLimit-Remaining": "0",
                "RateLimit-Reset": "1700000000",
            },
        )
        self.client = created_test_client(transport=self.transport)

    async def when_get_mr_is_called(self):
        self.error = None
        try:
            await self.client.get_mr(42)
        except GitLabRateLimitError as e:
            self.error = e

    def then_rate_limit_error_should_be_raised(self):
        assert self.error is not None
        assert isinstance(self.error, GitLabRateLimitError)

    def and_status_code_should_be_429(self):
        assert self.error.status_code == 429

    def and_retry_after_should_be_set(self):
        assert self.error.retry_after == 60

    async def do_cleanup(self):
        if hasattr(self, "client"):
            await self.client.close()
