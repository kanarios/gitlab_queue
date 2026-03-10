"""Test scenario: get_pipeline_jobs fetches all pages via x-next-page header."""

from __future__ import annotations

import json
import re

import httpx
import vedro

from scenarios.contexts.gitlab_client_factory import TEST_PROJECT_ID, created_test_client
from scenarios.transports import GitLabMockTransport

from ._helpers import create_job_response


class Scenario(vedro.Scenario):
    subject = "get_pipeline_jobs fetches all pages when x-next-page header is present"

    def given_mock_gitlab_with_paginated_jobs(self):
        self.transport = GitLabMockTransport()

        page1_jobs = [
            create_job_response(1, name="lint", status="success"),
            create_job_response(2, name="test", status="success"),
        ]
        page2_jobs = [
            create_job_response(3, name="build", status="failed"),
        ]

        def handler(request: httpx.Request) -> httpx.Response:
            page = request.url.params.get("page", "1")
            if page == "1":
                return httpx.Response(
                    status_code=200,
                    content=json.dumps(page1_jobs).encode(),
                    headers={"content-type": "application/json", "x-next-page": "2"},
                )
            return httpx.Response(
                status_code=200,
                content=json.dumps(page2_jobs).encode(),
                headers={"content-type": "application/json", "x-next-page": ""},
            )

        self.transport.register_handler(
            "GET",
            re.compile(rf"/api/v4/projects/{TEST_PROJECT_ID}/pipelines/456/jobs"),
            handler,
        )
        self.client = created_test_client(transport=self.transport)

    async def when_get_pipeline_jobs_is_called(self):
        self.result = await self.client.get_pipeline_jobs(456)

    def then_all_three_jobs_are_returned(self):
        assert len(self.result) == 3

    def and_jobs_are_in_order(self):
        assert [j.id for j in self.result] == [1, 2, 3]

    def and_transport_received_two_requests(self):
        requests = self.transport.get_requests("GET", "/pipelines/456/jobs")
        assert len(requests) == 2

    async def do_cleanup(self):
        await self.client.close()
