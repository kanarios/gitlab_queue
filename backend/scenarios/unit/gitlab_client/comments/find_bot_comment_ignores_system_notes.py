"""Test scenario: _find_bot_comment ignores system notes with signature."""

from __future__ import annotations

import vedro
from scenarios.contexts.gitlab_client_factory import TEST_PROJECT_ID, create_test_client
from scenarios.contexts.jj_gitlab_mock import mocked_gitlab_get_notes

from gitlab_queue.clients.gitlab import GitLabClient

from ._helpers import create_note_response


class Scenario(vedro.Scenario):
    subject = "_find_bot_comment ignores system notes with signature"

    async def given_mock_gitlab_with_system_note(self):
        # System note that happens to contain the signature (edge case)
        self.notes_data = [
            create_note_response(
                1,
                f"{GitLabClient.BOT_COMMENT_SIGNATURE}\nSystem generated",
                system=True,
            ),
        ]
        self._mock_ctx = mocked_gitlab_get_notes(TEST_PROJECT_ID, 42, self.notes_data)
        await self._mock_ctx.__aenter__()
        self.client = create_test_client()

    async def when_find_bot_comment_is_called(self):
        self.result = await self.client._find_bot_comment(42)

    def then_result_should_be_none(self):
        # System notes should be ignored even if they contain signature
        assert self.result is None

    async def do_cleanup(self):
        await self.client.close()
        await self._mock_ctx.__aexit__(None, None, None)
