"""Test scenario: _parse_retry_after returns integer for valid header."""

from __future__ import annotations

import httpx
import vedro

from scenarios.contexts.gitlab_client_factory import created_test_client
from scenarios.transports import GitLabMockTransport


class Scenario(vedro.Scenario):
    subject = "_parse_retry_after returns integer for valid Retry-After header"

    def given_response_with_retry_after_header(self):
        """
        Prepare a test HTTP 429 response containing a Retry-After header and initialize the test transport and client.

        This sets:
        - self.transport: a GitLabMockTransport instance
        - self.client: a test client created with the transport
        - self.response: an httpx.Response with status 429, header "Retry-After" set to "30", and an associated GET request to "http://test"
        """
        self.transport = GitLabMockTransport()
        self.client = created_test_client(transport=self.transport)
        self.response = httpx.Response(
            429,
            headers={"Retry-After": "30"},
            request=httpx.Request("GET", "http://test"),
        )

    def when_parse_retry_after_is_called(self):
        """
        Invoke the client's _parse_retry_after with the prepared response.

        Stores the parsed Retry-After value (as an integer) on self.result.
        """
        self.result = self.client._parse_retry_after(self.response)

    def then_result_should_be_30(self):
        assert self.result == 30

    async def do_cleanup(self):
        """
        Close the test HTTP client and release its resources.

        Performs an asynchronous shutdown of the underlying test client's connections.
        """
        await self.client.close()
