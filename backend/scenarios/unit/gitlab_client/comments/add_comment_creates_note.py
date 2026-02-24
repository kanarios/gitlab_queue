"""Test scenario: add_comment creates a new note."""

from __future__ import annotations

import vedro
from scenarios.contexts.gitlab_client_factory import TEST_PROJECT_ID, created_test_client
from scenarios.transports import GitLabMockTransport
from scenarios.transports.responses import note_response


class Scenario(vedro.Scenario):
    subject = "add_comment creates a new note"

    def given_mock_gitlab_for_adding_comment(self):
        self.transport = GitLabMockTransport()
        self.transport.register_post(
            f"/api/v4/projects/{TEST_PROJECT_ID}/merge_requests/42/notes",
            json_data=note_response(note_id=123, body="Test comment body"),
        )
        self.client = created_test_client(transport=self.transport)

    async def when_add_comment_is_called(self):
        self.result = await self.client.add_comment(42, "Test comment body")

    def then_result_should_be_note(self):
        assert self.result is not None

    def and_note_id_should_be_returned(self):
        assert self.result.id == 123

    async def do_cleanup(self):
        if hasattr(self, "client"):
            await self.client.close()
