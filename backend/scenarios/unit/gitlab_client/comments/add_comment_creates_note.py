"""Test scenario: add_comment creates a new note."""

from __future__ import annotations

import vedro
from scenarios.contexts.gitlab_client_factory import TEST_PROJECT_ID, create_test_client
from scenarios.contexts.jj_gitlab_mock import mocked_gitlab_add_comment


class Scenario(vedro.Scenario):
    subject = "add_comment creates a new note"

    async def given_mock_gitlab_for_adding_comment(self):
        self._mock_ctx = mocked_gitlab_add_comment(TEST_PROJECT_ID, 42, note_id=123)
        await self._mock_ctx.__aenter__()
        self.client = create_test_client()

    async def when_add_comment_is_called(self):
        self.result = await self.client.add_comment(42, "Test comment body")

    def then_result_should_be_note(self):
        assert self.result is not None

    def and_note_id_should_be_returned(self):
        assert self.result.id == 123

    async def do_cleanup(self):
        await self.client.close()
        await self._mock_ctx.__aexit__(None, None, None)
