"""Test scenario: _find_bot_comment finds comment with bot signature."""

from __future__ import annotations

import vedro
from scenarios.contexts.gitlab_client_factory import TEST_PROJECT_ID, created_test_client
from scenarios.transports import GitLabMockTransport

from gitlab_queue.clients.gitlab import GitLabClient

from ._helpers import create_note_response


class Scenario(vedro.Scenario):
    subject = "_find_bot_comment finds comment with bot signature"

    def given_mock_gitlab_with_bot_comment(self):
        self.notes_data = [
            create_note_response(1, "Regular comment"),
            create_note_response(
                2,
                f"{GitLabClient.BOT_COMMENT_SIGNATURE}\nBot status message",
            ),
            create_note_response(3, "Another comment"),
        ]
        self.transport = GitLabMockTransport()
        self.transport.register_get(
            f"/api/v4/projects/{TEST_PROJECT_ID}/merge_requests/42/notes",
            json_data=self.notes_data,
        )
        self.client = created_test_client(transport=self.transport)

    async def when_find_bot_comment_is_called(self):
        self.result = await self.client._find_bot_comment(42)

    def then_bot_comment_should_be_found(self):
        assert self.result is not None

    def and_note_id_should_be_2(self):
        assert self.result.id == 2

    def and_body_should_contain_signature(self):
        assert GitLabClient.BOT_COMMENT_SIGNATURE in self.result.body

    async def do_cleanup(self):
        await self.client.close()
