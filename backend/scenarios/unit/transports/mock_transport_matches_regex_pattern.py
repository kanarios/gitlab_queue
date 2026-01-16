"""Test: GitLabMockTransport matches regex pattern."""

import re

import httpx
import vedro
from scenarios.transports import GitLabMockTransport


class Scenario(vedro.Scenario):
    subject = "mock transport matches regex pattern"

    def given_transport_with_regex_pattern(self):
        self.transport = GitLabMockTransport()
        self.transport.register_get(
            re.compile(r"/api/v4/projects/\d+/merge_requests/\d+"),
            json_data={"iid": 99, "matched": True},
        )

    async def when_request_matches_pattern(self):
        async with httpx.AsyncClient(
            base_url="https://gitlab.example.com",
            transport=self.transport,
        ) as client:
            self.response = await client.get("/api/v4/projects/456/merge_requests/789")

    def then_response_should_have_status_200(self):
        assert self.response.status_code == 200

    def then_response_should_have_matched_data(self):
        data = self.response.json()
        assert data["matched"] is True
