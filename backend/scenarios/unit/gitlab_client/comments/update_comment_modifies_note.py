"""Test scenario: update_comment modifies existing note."""

from __future__ import annotations

import vedro
from scenarios.contexts.gitlab_client_factory import TEST_PROJECT_ID, create_test_client
from scenarios.contexts.jj_gitlab_mock import mocked_gitlab_update_comment


class Scenario(vedro.Scenario):
    subject = "update_comment modifies existing note"

    async def given_mock_gitlab_for_updating_comment(self):
        self._mock_ctx = mocked_gitlab_update_comment(TEST_PROJECT_ID, 42, note_id=456)
        await self._mock_ctx.__aenter__()
        self.client = create_test_client()

    async def when_update_comment_is_called(self):
        self.result = await self.client.update_comment(42, 456, "Updated comment body")

    def then_result_should_be_note(self):
        assert self.result is not None

    def and_note_id_should_match(self):
        assert self.result.id == 456

    async def do_cleanup(self):
        await self.client.close()
        await self._mock_ctx.__aexit__(None, None, None)
