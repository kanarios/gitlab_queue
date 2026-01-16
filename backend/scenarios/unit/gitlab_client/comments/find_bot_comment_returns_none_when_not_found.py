"""Test scenario: _find_bot_comment returns None when no bot comment."""

from __future__ import annotations

import vedro
from scenarios.contexts.gitlab_client_factory import TEST_PROJECT_ID, created_test_client
from scenarios.transports import GitLabMockTransport

from ._helpers import create_note_response


class Scenario(vedro.Scenario):
    subject = "_find_bot_comment returns None when no bot comment"

    def given_mock_gitlab_without_bot_comment(self):
        self.notes_data = [
            create_note_response(1, "Regular comment 1"),
            create_note_response(2, "Regular comment 2"),
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
        assert self.result is None

    async def do_cleanup(self):
        await self.client.close()
