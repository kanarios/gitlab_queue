"""Test scenario: add_or_update_pinned_comment creates new when none exists."""

from __future__ import annotations

import vedro
from scenarios.contexts.gitlab_client_factory import TEST_PROJECT_ID, create_test_client
from scenarios.contexts.jj_gitlab_mock import mocked_gitlab_add_comment, mocked_gitlab_get_notes


class Scenario(vedro.Scenario):
    subject = "add_or_update_pinned_comment creates new when none exists"

    async def given_mock_gitlab_without_existing_comment(self):
        # First mock: no existing notes
        self._notes_mock = mocked_gitlab_get_notes(TEST_PROJECT_ID, 42, [])
        await self._notes_mock.__aenter__()
        # Second mock: add comment endpoint
        self._add_mock = mocked_gitlab_add_comment(TEST_PROJECT_ID, 42, note_id=999)
        await self._add_mock.__aenter__()
        self.client = create_test_client()

    async def when_add_or_update_is_called(self):
        self.result = await self.client.add_or_update_pinned_comment(42, "Status update")

    def then_note_should_be_created(self):
        assert self.result is not None

    def and_note_id_should_be_returned(self):
        assert self.result.id == 999

    async def do_cleanup(self):
        await self.client.close()
        await self._add_mock.__aexit__(None, None, None)
        await self._notes_mock.__aexit__(None, None, None)
