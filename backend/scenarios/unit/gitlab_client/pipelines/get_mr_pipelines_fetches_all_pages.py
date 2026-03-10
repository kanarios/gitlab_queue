"""Test scenario: get_mr_pipelines fetches all pages via x-next-page header."""

from __future__ import annotations

import json
import re

import httpx
import vedro

from scenarios.contexts.gitlab_client_factory import TEST_PROJECT_ID, created_test_client
from scenarios.transports import GitLabMockTransport

from ._helpers import create_pipeline_response


class Scenario(vedro.Scenario):
    subject = "get_mr_pipelines fetches all pages when x-next-page header is present"

    def given_mock_gitlab_with_paginated_pipelines(self):
        self.transport = GitLabMockTransport()

        page1_pipelines = [
            create_pipeline_response(100, status="success"),
            create_pipeline_response(99, status="failed"),
        ]
        page2_pipelines = [
            create_pipeline_response(98, status="canceled"),
        ]

        def handler(request: httpx.Request) -> httpx.Response:
            page = request.url.params.get("page", "1")
            if page == "1":
                return httpx.Response(
                    status_code=200,
                    content=json.dumps(page1_pipelines).encode(),
                    headers={"content-type": "application/json", "x-next-page": "2"},
                )
            return httpx.Response(
                status_code=200,
                content=json.dumps(page2_pipelines).encode(),
                headers={"content-type": "application/json", "x-next-page": ""},
            )

        self.transport.register_handler(
            "GET",
            re.compile(rf"/api/v4/projects/{TEST_PROJECT_ID}/merge_requests/42/pipelines"),
            handler,
        )
        self.client = created_test_client(transport=self.transport)

    async def when_get_mr_pipelines_is_called(self):
        self.result = await self.client.get_mr_pipelines(42)

    def then_all_three_pipelines_are_returned(self):
        assert len(self.result) == 3

    def and_pipelines_are_in_order(self):
        assert [p.id for p in self.result] == [100, 99, 98]

    def and_transport_received_two_requests(self):
        requests = self.transport.get_requests("GET", "/merge_requests/42/pipelines")
        assert len(requests) == 2

    async def do_cleanup(self):
        await self.client.close()
