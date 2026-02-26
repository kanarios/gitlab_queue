"""Test scenario: _parse_retry_after returns None for invalid header."""

from __future__ import annotations

import httpx
import vedro

from scenarios.contexts.gitlab_client_factory import created_test_client
from scenarios.transports import GitLabMockTransport


class Scenario(vedro.Scenario):
    subject = "_parse_retry_after returns None for invalid Retry-After header"

    def given_response_with_invalid_retry_after_header(self):
        """
        Set up a test HTTP 429 response with an invalid Retry-After header and initialize the mock transport and test client.

        Initializes:
        - self.transport: GitLabMockTransport instance used for the test client.
        - self.client: test client created with the mock transport.
        - self.response: httpx.Response with status 429, header "Retry-After" set to "invalid", and an associated httpx.Request.
        """
        self.transport = GitLabMockTransport()
        self.client = created_test_client(transport=self.transport)
        self.response = httpx.Response(
            429,
            headers={"Retry-After": "invalid"},
            request=httpx.Request("GET", "http://test"),
        )

    def when_parse_retry_after_is_called(self):
        self.result = self.client._parse_retry_after(self.response)

    def then_result_should_be_none(self):
        """
        Asserts that the parsed Retry-After value is None.

        Raises:
            AssertionError: If `self.result` is not `None`.
        """
        assert self.result is None

    async def do_cleanup(self):
        """
        Close the test HTTP client created for the scenario.

        Closes the client's open connections and releases associated resources.
        """
        await self.client.close()
