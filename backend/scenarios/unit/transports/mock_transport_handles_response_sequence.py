"""Test: GitLabMockTransport handles response sequence."""

import httpx
import vedro
from scenarios.transports import GitLabMockTransport
from scenarios.transports.gitlab_mock_transport import create_json_response


class Scenario(vedro.Scenario):
    subject = "mock transport handles response sequence"

    def given_transport_with_sequence(self):
        self.transport = GitLabMockTransport()
        self.transport.register_sequence(
            "GET",
            "/api/v4/projects/123/pipelines/1",
            responses=[
                create_json_response(json_data={"status": "running"}),
                create_json_response(json_data={"status": "running"}),
                create_json_response(json_data={"status": "success"}),
            ],
        )

    async def when_multiple_requests_are_made(self):
        self.responses = []
        async with httpx.AsyncClient(
            base_url="https://gitlab.example.com",
            transport=self.transport,
        ) as client:
            for _ in range(4):  # 4th call should return 404
                resp = await client.get("/api/v4/projects/123/pipelines/1")
                self.responses.append(resp)

    def then_first_response_should_be_running(self):
        assert self.responses[0].json()["status"] == "running"

    def then_second_response_should_be_running(self):
        assert self.responses[1].json()["status"] == "running"

    def then_third_response_should_be_success(self):
        assert self.responses[2].json()["status"] == "success"

    def then_fourth_response_should_be_404(self):
        assert self.responses[3].status_code == 404
