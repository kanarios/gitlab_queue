"""Test scenario: _parse_retry_after returns None for invalid header."""

from __future__ import annotations

import httpx
import vedro
from scenarios.contexts.gitlab_client_factory import created_test_client
from scenarios.transports import GitLabMockTransport


class Scenario(vedro.Scenario):
    subject = "_parse_retry_after returns None for invalid Retry-After header"

    def given_response_with_invalid_retry_after_header(self):
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
        assert self.result is None

    async def do_cleanup(self):
        await self.client.close()
