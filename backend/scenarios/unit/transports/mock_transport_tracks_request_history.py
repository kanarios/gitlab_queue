"""Test: GitLabMockTransport tracks request history."""

import httpx
import vedro
from scenarios.transports import GitLabMockTransport


class Scenario(vedro.Scenario):
    subject = "mock transport tracks request history"

    def given_transport_with_post_handler(self):
        self.transport = GitLabMockTransport()
        self.transport.register_post(
            "/api/v4/projects/123/merge_requests/42/notes",
            json_data={"id": 1, "body": "Created"},
        )

    async def when_post_request_with_json_body(self):
        async with httpx.AsyncClient(
            base_url="https://gitlab.example.com",
            transport=self.transport,
        ) as client:
            self.response = await client.post(
                "/api/v4/projects/123/merge_requests/42/notes",
                json={"body": "Test comment"},
            )

    def then_request_should_be_in_history(self):
        self.transport.assert_called_once()

    def then_request_body_should_be_accessible(self):
        request_json = self.transport.get_request_json()
        assert request_json["body"] == "Test comment"

    def and_request_path_should_be_tracked(self):
        self.transport.assert_called_with_path("/api/v4/projects/123/merge_requests/42/notes")
