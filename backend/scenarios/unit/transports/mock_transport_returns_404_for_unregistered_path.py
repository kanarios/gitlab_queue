"""Test: GitLabMockTransport returns 404 for unregistered path."""

import httpx
import vedro
from scenarios.transports import GitLabMockTransport


class Scenario(vedro.Scenario):
    subject = "mock transport returns 404 for unregistered path"

    def given_empty_transport(self):
        self.transport = GitLabMockTransport()

    async def when_request_to_unregistered_path(self):
        async with httpx.AsyncClient(
            base_url="https://gitlab.example.com",
            transport=self.transport,
        ) as client:
            self.response = await client.get("/api/v4/projects/123/unknown")

    def then_response_should_have_status_404(self):
        assert self.response.status_code == 404

    def then_response_should_have_error_message(self):
        data = self.response.json()
        assert "No mock registered" in data["message"]
        assert "/api/v4/projects/123/unknown" in data["message"]
