"""Test scenario: _find_bot_comment returns None when no bot comment."""

from __future__ import annotations

import vedro
from scenarios.contexts.gitlab_client_factory import TEST_PROJECT_ID, create_test_client
from scenarios.contexts.jj_gitlab_mock import mocked_gitlab_get_notes

from ._helpers import create_note_response


class Scenario(vedro.Scenario):
    subject = "_find_bot_comment returns None when no bot comment"

    async def given_mock_gitlab_without_bot_comment(self):
        self.notes_data = [
            create_note_response(1, "Regular comment 1"),
            create_note_response(2, "Regular comment 2"),
        ]
        self._mock_ctx = mocked_gitlab_get_notes(TEST_PROJECT_ID, 42, self.notes_data)
        await self._mock_ctx.__aenter__()
        self.client = create_test_client()

    async def when_find_bot_comment_is_called(self):
        self.result = await self.client._find_bot_comment(42)

    def then_result_should_be_none(self):
        assert self.result is None

    async def do_cleanup(self):
        await self.client.close()
        await self._mock_ctx.__aexit__(None, None, None)
