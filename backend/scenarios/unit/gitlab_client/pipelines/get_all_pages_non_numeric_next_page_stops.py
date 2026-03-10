"""Test scenario: get_all_pages stops on non-numeric x-next-page header."""

from __future__ import annotations

import json
import re

import httpx
import vedro

from scenarios.contexts.gitlab_client_factory import TEST_PROJECT_ID, created_test_client
from scenarios.transports import GitLabMockTransport


class Scenario(vedro.Scenario):
    subject = "get_all_pages stops gracefully on non-numeric x-next-page header"

    def given_mock_gitlab_returns_invalid_next_page(self):
        self.transport = GitLabMockTransport()

        items = [{"id": 1}, {"id": 2}]

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                status_code=200,
                content=json.dumps(items).encode(),
                headers={
                    "content-type": "application/json",
                    "x-next-page": "invalid",
                },
            )

        self.transport.register_handler(
            "GET",
            re.compile(rf"/api/v4/projects/{TEST_PROJECT_ID}/test/endpoint"),
            handler,
        )
        self.client = created_test_client(transport=self.transport)

    async def when_get_all_pages_is_called(self):
        self.result = await self.client.get_all_pages("/test/endpoint")

    def then_first_page_data_is_returned(self):
        assert len(self.result) == 2

    def and_data_matches_first_page_items(self):
        assert [item["id"] for item in self.result] == [1, 2]

    def and_only_one_request_was_made(self):
        requests = self.transport.get_requests("GET", "/test/endpoint")
        assert len(requests) == 1

    async def do_cleanup(self):
        await self.client.close()
