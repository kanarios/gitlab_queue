"""Test: GitLabMockTransport registers GET response."""

import httpx
import vedro
from scenarios.transports import GitLabMockTransport


class Scenario(vedro.Scenario):
    subject = "mock transport registers GET response"

    def given_transport_with_registered_get(self):
        self.transport = GitLabMockTransport()
        self.transport.register_get(
            "/api/v4/projects/123/merge_requests/42",
            json_data={"iid": 42, "title": "Test MR"},
        )

    async def when_request_is_made(self):
        async with httpx.AsyncClient(
            base_url="https://gitlab.example.com",
            transport=self.transport,
        ) as client:
            self.response = await client.get("/api/v4/projects/123/merge_requests/42")

    def then_response_should_have_status_200(self):
        assert self.response.status_code == 200

    def then_response_should_have_json_body(self):
        data = self.response.json()
        assert data["iid"] == 42
        assert data["title"] == "Test MR"

    def and_request_should_be_in_history(self):
        assert self.transport.call_count == 1
        assert self.transport.get_request().url.path == "/api/v4/projects/123/merge_requests/42"
