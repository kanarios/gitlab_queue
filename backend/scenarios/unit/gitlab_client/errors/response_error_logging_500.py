"""Test scenario: _handle_error_response raises GitLabServerError on 500."""

from __future__ import annotations

import httpx
import vedro

from gitlab_queue.clients.gitlab import GitLabServerError
from scenarios.contexts.gitlab_client_factory import created_test_client
from scenarios.transports import GitLabMockTransport


class Scenario(vedro.Scenario):
    subject = "_handle_error_response raises GitLabServerError on 500"

    def given_mock_response_with_500(self):
        """
        Prepare a test GitLab client and an HTTP 500 response for the scenario.

        Sets self.transport to a GitLabMockTransport, self.client to a test GitLab client using that transport, and self.response to an httpx.Response with status code 500 and a JSON body containing a "message" key.
        """
        self.transport = GitLabMockTransport()
        self.client = created_test_client(transport=self.transport)
        self.response = httpx.Response(
            500,
            json={"message": "Internal Server Error"},
            request=httpx.Request("GET", "http://test/api/v4/projects/123/merge_requests/1"),
        )

    def when_handle_error_response_is_called(self):
        """
        Invokes the client's error handler with the prepared response and captures a raised GitLabServerError.

        If GitLabServerError is raised by _handle_error_response, assigns the exception to self.error; otherwise leaves self.error as None.
        """
        self.error = None
        try:
            self.client._handle_error_response(self.response)
        except GitLabServerError as e:
            self.error = e

    def then_server_error_should_be_raised(self):
        assert self.error is not None

    def and_status_code_should_be_500(self):
        """
        Asserts that the captured error's HTTP status code equals 500.
        """
        assert self.error.status_code == 500

    def and_response_body_should_be_available(self):
        """
        Verifies the raised error includes a JSON response body containing a "message" key.

        Asserts that self.error.response_body is not None, is a dict, and contains the "message" key.
        """
        assert self.error.response_body is not None
        assert isinstance(self.error.response_body, dict)
        assert "message" in self.error.response_body

    async def do_cleanup(self):
        """
        Closes the test GitLab client to release network resources.

        This awaits the client's close coroutine to ensure any open connections are terminated before the scenario ends.
        """
        await self.client.close()
