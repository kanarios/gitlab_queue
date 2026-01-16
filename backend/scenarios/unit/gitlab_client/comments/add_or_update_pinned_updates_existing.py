"""Test scenario: add_or_update_pinned_comment updates existing bot comment."""

from __future__ import annotations

import vedro
from scenarios.contexts.gitlab_client_factory import TEST_PROJECT_ID, create_test_client
from scenarios.contexts.jj_gitlab_mock import mocked_gitlab_get_notes, mocked_gitlab_update_comment

from gitlab_queue.clients.gitlab import GitLabClient

from ._helpers import create_note_response


class Scenario(vedro.Scenario):
    subject = "add_or_update_pinned_comment updates existing bot comment"

    async def given_mock_gitlab_with_existing_bot_comment(self):
        # Mock: existing bot comment
        notes_data = [
            create_note_response(
                777,
                f"{GitLabClient.BOT_COMMENT_SIGNATURE}\nOld status",
            ),
        ]
        self._notes_mock = mocked_gitlab_get_notes(TEST_PROJECT_ID, 42, notes_data)
        await self._notes_mock.__aenter__()
        # Mock: update comment endpoint
        self._update_mock = mocked_gitlab_update_comment(TEST_PROJECT_ID, 42, note_id=777)
        await self._update_mock.__aenter__()
        self.client = create_test_client()

    async def when_add_or_update_is_called(self):
        self.result = await self.client.add_or_update_pinned_comment(42, "New status")

    def then_note_should_be_updated(self):
        assert self.result is not None

    def and_note_id_should_match_existing(self):
        assert self.result.id == 777

    async def do_cleanup(self):
        await self.client.close()
        await self._update_mock.__aexit__(None, None, None)
        await self._notes_mock.__aexit__(None, None, None)
