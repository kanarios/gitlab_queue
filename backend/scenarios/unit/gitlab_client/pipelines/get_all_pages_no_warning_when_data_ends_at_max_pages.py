"""Test scenario: no safety cap warning when data ends exactly at max_pages."""

from __future__ import annotations

import json
import re

import httpx
import structlog.testing
import vedro

from scenarios.contexts.gitlab_client_factory import TEST_PROJECT_ID, created_test_client
from scenarios.transports import GitLabMockTransport

from ._helpers import create_job_response


class Scenario(vedro.Scenario):
    subject = "get_all_pages does not warn when data ends exactly at max_pages"

    def given_mock_gitlab_with_exactly_two_pages(self):
        self.transport = GitLabMockTransport()

        page1_jobs = [create_job_response(1, name="lint", status="success")]
        page2_jobs = [create_job_response(2, name="test", status="success")]

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
            re.compile(rf"/api/v4/projects/{TEST_PROJECT_ID}/pipelines/300/jobs"),
            handler,
        )
        self.client = created_test_client(transport=self.transport)

    async def when_get_all_pages_is_called_with_max_pages_2(self):
        with structlog.testing.capture_logs() as self.captured:
            self.result = await self.client.get_all_pages(
                "/pipelines/300/jobs",
                max_pages=2,
            )

    def then_all_items_are_returned(self):
        assert len(self.result) == 2

    def and_no_safety_cap_warning_is_emitted(self):
        cap_warnings = [e for e in self.captured if e.get("event") == "Pagination safety cap reached"]
        assert cap_warnings == []

    async def do_cleanup(self):
        await self.client.close()
