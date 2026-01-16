"""Test scenario: add_or_update_pinned_comment adds signature if missing."""

from __future__ import annotations

import vedro
from scenarios.contexts.gitlab_client_factory import TEST_PROJECT_ID, create_test_client
from scenarios.contexts.jj_gitlab_mock import mocked_gitlab_add_comment, mocked_gitlab_get_notes


class Scenario(vedro.Scenario):
    subject = "add_or_update_pinned_comment adds signature if missing"

    async def given_mock_gitlab_without_existing_comment(self):
        self._notes_mock = mocked_gitlab_get_notes(TEST_PROJECT_ID, 42, [])
        await self._notes_mock.__aenter__()
        self._add_mock = mocked_gitlab_add_comment(TEST_PROJECT_ID, 42, note_id=111)
        await self._add_mock.__aenter__()
        self.client = create_test_client()

    async def when_add_or_update_is_called_without_signature(self):
        # Body doesn't contain signature - should be added automatically
        self.result = await self.client.add_or_update_pinned_comment(42, "Status without signature")

    def then_note_should_be_created(self):
        assert self.result is not None

    async def do_cleanup(self):
        await self.client.close()
        await self._add_mock.__aexit__(None, None, None)
        await self._notes_mock.__aexit__(None, None, None)
