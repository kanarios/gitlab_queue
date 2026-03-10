"""Test scenario: get_all_pages stops fetching at max_pages safety cap."""

from __future__ import annotations

import json
import re

import httpx
import vedro

from scenarios.contexts.gitlab_client_factory import TEST_PROJECT_ID, created_test_client
from scenarios.transports import GitLabMockTransport


class Scenario(vedro.Scenario):
    subject = "get_all_pages stops fetching at max_pages safety cap"

    def given_mock_gitlab_always_returns_next_page(self):
        self.transport = GitLabMockTransport()

        def handler(request: httpx.Request) -> httpx.Response:
            page = int(request.url.params.get("page", "1"))
            items = [{"id": page}]
            return httpx.Response(
                status_code=200,
                content=json.dumps(items).encode(),
                headers={
                    "content-type": "application/json",
                    "x-next-page": str(page + 1),
                },
            )

        self.transport.register_handler(
            "GET",
            re.compile(rf"/api/v4/projects/{TEST_PROJECT_ID}/test/endpoint"),
            handler,
        )
        self.client = created_test_client(transport=self.transport)

    async def when_get_all_pages_is_called_with_max_pages_3(self):
        self.result = await self.client.get_all_pages("/test/endpoint", max_pages=3)

    def then_exactly_three_pages_of_data_are_returned(self):
        assert len(self.result) == 3

    def and_data_contains_items_from_pages_1_through_3(self):
        assert [item["id"] for item in self.result] == [1, 2, 3]

    def and_transport_received_three_requests(self):
        requests = self.transport.get_requests("GET", "/test/endpoint")
        assert len(requests) == 3

    async def do_cleanup(self):
        await self.client.close()
