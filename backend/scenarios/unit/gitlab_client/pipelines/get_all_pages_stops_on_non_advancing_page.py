"""Test scenario: get_all_pages stops when server returns non-advancing x-next-page."""

from __future__ import annotations

import json
import re

import httpx
import vedro

from scenarios.contexts.gitlab_client_factory import TEST_PROJECT_ID, created_test_client
from scenarios.transports import GitLabMockTransport

from ._helpers import create_job_response


class Scenario(vedro.Scenario):
    subject = "get_all_pages stops when x-next-page does not advance"

    def given_mock_gitlab_returning_same_page(self):
        self.transport = GitLabMockTransport()

        jobs = [create_job_response(1, name="lint", status="success")]

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                status_code=200,
                content=json.dumps(jobs).encode(),
                headers={"content-type": "application/json", "x-next-page": "1"},
            )

        self.transport.register_handler(
            "GET",
            re.compile(rf"/api/v4/projects/{TEST_PROJECT_ID}/pipelines/100/jobs"),
            handler,
        )
        self.client = created_test_client(transport=self.transport)

    async def when_get_all_pages_is_called(self):
        self.result = await self.client.get_all_pages("/pipelines/100/jobs")

    def then_only_first_page_items_are_returned(self):
        assert len(self.result) == 1

    def and_transport_received_only_one_request(self):
        requests = self.transport.get_requests("GET", "/pipelines/100/jobs")
        assert len(requests) == 1

    async def do_cleanup(self):
        await self.client.close()
