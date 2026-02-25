"""Test scenario: _find_bot_comment ignores system notes with signature."""

from __future__ import annotations

import vedro
from scenarios.contexts.gitlab_client_factory import TEST_PROJECT_ID, created_test_client
from scenarios.transports import GitLabMockTransport

from gitlab_queue.clients.gitlab import GitLabClient

from ._helpers import create_note_response


class Scenario(vedro.Scenario):
    subject = "_find_bot_comment ignores system notes with signature"

    def given_mock_gitlab_with_system_note(self):
        # System note that happens to contain the signature (edge case)
        self.notes_data = [
            create_note_response(
                1,
                f"{GitLabClient.BOT_COMMENT_SIGNATURE}\nSystem generated",
                system=True,
            ),
        ]
        self.transport = GitLabMockTransport()
        self.transport.register_get(
            f"/api/v4/projects/{TEST_PROJECT_ID}/merge_requests/42/notes",
            json_data=self.notes_data,
        )
        self.client = created_test_client(transport=self.transport)

    async def when_find_bot_comment_is_called(self):
        self.result = await self.client._find_bot_comment(42)

    def then_result_should_be_none(self):
        # System notes should be ignored even if they contain signature
        assert self.result is None

    async def do_cleanup(self):
        await self.client.close()
