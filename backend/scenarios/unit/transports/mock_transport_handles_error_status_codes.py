"""Test: GitLabMockTransport handles error status codes."""

import vedro
from scenarios.contexts.gitlab_client_factory import created_test_settings
from scenarios.transports import GitLabMockTransport
from scenarios.transports.responses import not_found_response

from gitlab_queue.clients.gitlab import GitLabClient, GitLabNotFoundError


class Scenario(vedro.Scenario):
    subject = "mock transport handles error status codes"

    def given_transport_with_404_response(self):
        self.transport = GitLabMockTransport()
        self.transport.register_get(
            "/api/v4/projects/123/merge_requests/999",
            status=404,
            json_data=not_found_response("MR not found"),
        )

    def given_gitlab_client_with_transport(self):
        settings = created_test_settings(project_id=123)
        self.client = GitLabClient(settings, transport=self.transport)

    async def when_get_mr_is_called(self):
        self.exception = None
        try:
            await self.client.get_mr(999)
        except GitLabNotFoundError as e:
            self.exception = e

    def then_should_raise_not_found_error(self):
        assert self.exception is not None
        assert isinstance(self.exception, GitLabNotFoundError)

    def then_error_should_have_status_code(self):
        assert self.exception.status_code == 404

    async def cleanup(self):
        await self.client.close()
