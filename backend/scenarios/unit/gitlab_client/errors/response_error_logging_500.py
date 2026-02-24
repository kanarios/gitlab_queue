"""Test scenario: _handle_error_response raises GitLabServerError on 500."""

from __future__ import annotations

import httpx
import vedro
from scenarios.contexts.gitlab_client_factory import created_test_client
from scenarios.transports import GitLabMockTransport

from gitlab_queue.clients.gitlab import GitLabServerError


class Scenario(vedro.Scenario):
    subject = "_handle_error_response raises GitLabServerError on 500"

    def given_mock_response_with_500(self):
        self.transport = GitLabMockTransport()
        self.client = created_test_client(transport=self.transport)
        self.response = httpx.Response(
            500,
            json={"message": "Internal Server Error"},
            request=httpx.Request("GET", "http://test/api/v4/projects/123/merge_requests/1"),
        )

    def when_handle_error_response_is_called(self):
        self.error = None
        try:
            self.client._handle_error_response(self.response)
        except GitLabServerError as e:
            self.error = e

    def then_server_error_should_be_raised(self):
        assert self.error is not None
        assert isinstance(self.error, GitLabServerError)

    def and_status_code_should_be_500(self):
        assert self.error.status_code == 500

    def and_response_body_should_be_available(self):
        assert self.error.response_body is not None
        assert isinstance(self.error.response_body, dict)
        assert "message" in self.error.response_body

    async def do_cleanup(self):
        if hasattr(self, "client"):
            await self.client.close()
