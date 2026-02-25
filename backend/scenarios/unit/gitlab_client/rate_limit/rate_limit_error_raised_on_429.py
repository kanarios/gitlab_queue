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
        """
        Configure a mock GitLab transport to return a 429 rate-limit response for a specific merge request and create a test client.
        
        Registers a GET handler for /api/v4/projects/{TEST_PROJECT_ID}/merge_requests/42 that responds with status 429, a rate-limit JSON payload, and headers including Retry-After: 60, RateLimit-Limit, RateLimit-Remaining, and RateLimit-Reset. Assigns the mock transport to self.transport and the created test client to self.client.
        """
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
        """
        Attempts to fetch merge request 42 and stores a caught GitLabRateLimitError on self.error.
        
        If a GitLabRateLimitError is raised by the client call, assigns that exception to self.error; otherwise leaves self.error as None.
        """
        self.error = None
        try:
            await self.client.get_mr(42)
        except GitLabRateLimitError as e:
            self.error = e

    def then_rate_limit_error_should_be_raised(self):
        """
        Asserts that a GitLabRateLimitError was raised and stored on self.error.
        
        Verifies that self.error is not None and is an instance of GitLabRateLimitError.
        """
        assert self.error is not None
        assert isinstance(self.error, GitLabRateLimitError)

    def and_status_code_should_be_429(self):
        """
        Asserts that the captured error has HTTP status code 429.
        
        Raises:
            AssertionError: If the captured error's status_code is not 429 or if no error is captured.
        """
        assert self.error.status_code == 429

    def and_retry_after_should_be_set(self):
        """
        Asserts the captured rate-limit error has a retry_after value of 60 seconds.
        """
        assert self.error.retry_after == 60

    async def do_cleanup(self):
        """
        Close the test GitLab client used by the scenario.
        
        Closes the client's network connections and releases any associated resources.
        """
        await self.client.close()
