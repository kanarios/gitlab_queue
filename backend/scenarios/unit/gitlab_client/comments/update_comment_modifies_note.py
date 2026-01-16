"""Test scenario: update_comment modifies existing note."""

from __future__ import annotations

import vedro
from scenarios.contexts.gitlab_client_factory import TEST_PROJECT_ID, created_test_client
from scenarios.transports import GitLabMockTransport
from scenarios.transports.responses import note_response


class Scenario(vedro.Scenario):
    subject = "update_comment modifies existing note"

    def given_mock_gitlab_for_updating_comment(self):
        self.transport = GitLabMockTransport()
        self.transport.register_put(
            f"/api/v4/projects/{TEST_PROJECT_ID}/merge_requests/42/notes/456",
            json_data=note_response(note_id=456, body="Updated comment body"),
        )
        self.client = created_test_client(transport=self.transport)

    async def when_update_comment_is_called(self):
        self.result = await self.client.update_comment(42, 456, "Updated comment body")

    def then_result_should_be_note(self):
        assert self.result is not None

    def and_note_id_should_match(self):
        assert self.result.id == 456

    async def do_cleanup(self):
        await self.client.close()
