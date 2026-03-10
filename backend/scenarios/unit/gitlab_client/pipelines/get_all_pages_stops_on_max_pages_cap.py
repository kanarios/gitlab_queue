"""Test scenario: get_all_pages stops when max_pages cap is reached."""

from __future__ import annotations

import json
import re

import httpx
import vedro

from scenarios.contexts.gitlab_client_factory import TEST_PROJECT_ID, created_test_client
from scenarios.transports import GitLabMockTransport

from ._helpers import create_job_response


class Scenario(vedro.Scenario):
    subject = "get_all_pages stops after fetching max_pages pages"

    def given_mock_gitlab_with_infinite_pages(self):
        self.transport = GitLabMockTransport()

        def handler(request: httpx.Request) -> httpx.Response:
            page = int(request.url.params.get("page", "1"))
            jobs = [create_job_response(page, name=f"job-{page}", status="success")]
            return httpx.Response(
                status_code=200,
                content=json.dumps(jobs).encode(),
                headers={
                    "content-type": "application/json",
                    "x-next-page": str(page + 1),
                },
            )

        self.transport.register_handler(
            "GET",
            re.compile(rf"/api/v4/projects/{TEST_PROJECT_ID}/pipelines/200/jobs"),
            handler,
        )
        self.client = created_test_client(transport=self.transport)

    async def when_get_all_pages_is_called_with_max_pages_2(self):
        self.result = await self.client.get_all_pages(
            "/pipelines/200/jobs",
            max_pages=2,
        )

    def then_only_two_pages_of_items_are_returned(self):
        assert len(self.result) == 2

    def and_transport_received_exactly_two_requests(self):
        requests = self.transport.get_requests("GET", "/pipelines/200/jobs")
        assert len(requests) == 2

    async def do_cleanup(self):
        await self.client.close()
