"""Test: GitLabMockTransport works with GitLabClient."""

import vedro
from scenarios.contexts.gitlab_client_factory import created_test_settings
from scenarios.transports import GitLabMockTransport
from scenarios.transports.responses import mr_response

from gitlab_queue.clients.gitlab import GitLabClient


class Scenario(vedro.Scenario):
    subject = "mock transport works with GitLabClient"

    def given_transport_with_mr_response(self):
        self.transport = GitLabMockTransport()
        self.transport.register_get(
            "/api/v4/projects/123/merge_requests/42",
            json_data=mr_response(
                iid=42,
                title="Feature: Add new button",
                state="opened",
                labels=["queue"],
            ),
        )

    def given_gitlab_client_with_transport(self):
        settings = created_test_settings(project_id=123)
        self.client = GitLabClient(settings, transport=self.transport)

    async def when_get_mr_is_called(self):
        self.mr = await self.client.get_mr(42)

    def then_mr_should_have_correct_iid(self):
        assert self.mr.iid == 42

    def then_mr_should_have_correct_title(self):
        assert self.mr.title == "Feature: Add new button"

    def then_mr_should_have_correct_state(self):
        assert self.mr.state == "opened"

    def then_mr_should_have_labels(self):
        assert "queue" in self.mr.labels

    def and_request_should_be_tracked(self):
        self.transport.assert_called_once()

    async def cleanup(self):
        await self.client.close()
