"""Test scenarios for GitLabClient comment operations.

Tests comment-related methods including:
- add_comment()
- update_comment()
- _find_bot_comment()
- add_or_update_pinned_comment()
"""

from __future__ import annotations

import vedro
from scenarios.contexts.gitlab_client_factory import TEST_PROJECT_ID, create_test_client
from scenarios.contexts.jj_gitlab_mock import (
    mock_gitlab_add_comment,
    mock_gitlab_get_notes,
    mock_gitlab_update_comment,
)

from gitlab_queue.clients.gitlab import GitLabClient


def create_note_response(
    note_id: int,
    body: str,
    author_id: int = 1,
    system: bool = False,
) -> dict:
    """Create a GitLab note API response for testing."""
    return {
        "id": note_id,
        "body": body,
        "system": system,
        "author": {
            "id": author_id,
            "name": "Test User",
            "username": "testuser",
        },
    }


class Scenario__add_comment_creates_note(vedro.Scenario):
    subject = "add_comment creates a new note"

    async def given_mock_gitlab_for_adding_comment(self):
        self._mock_ctx = mock_gitlab_add_comment(TEST_PROJECT_ID, 42, note_id=123)
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


class Scenario__update_comment_modifies_note(vedro.Scenario):
    subject = "update_comment modifies existing note"

    async def given_mock_gitlab_for_updating_comment(self):
        self._mock_ctx = mock_gitlab_update_comment(TEST_PROJECT_ID, 42, note_id=456)
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


class Scenario__find_bot_comment_finds_existing(vedro.Scenario):
    subject = "_find_bot_comment finds comment with bot signature"

    async def given_mock_gitlab_with_bot_comment(self):
        self.notes_data = [
            create_note_response(1, "Regular comment"),
            create_note_response(
                2,
                f"{GitLabClient.BOT_COMMENT_SIGNATURE}\nBot status message",
            ),
            create_note_response(3, "Another comment"),
        ]
        self._mock_ctx = mock_gitlab_get_notes(TEST_PROJECT_ID, 42, self.notes_data)
        await self._mock_ctx.__aenter__()
        self.client = create_test_client()

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
        await self._mock_ctx.__aexit__(None, None, None)


class Scenario__find_bot_comment_returns_none_when_not_found(vedro.Scenario):
    subject = "_find_bot_comment returns None when no bot comment"

    async def given_mock_gitlab_without_bot_comment(self):
        self.notes_data = [
            create_note_response(1, "Regular comment 1"),
            create_note_response(2, "Regular comment 2"),
        ]
        self._mock_ctx = mock_gitlab_get_notes(TEST_PROJECT_ID, 42, self.notes_data)
        await self._mock_ctx.__aenter__()
        self.client = create_test_client()

    async def when_find_bot_comment_is_called(self):
        self.result = await self.client._find_bot_comment(42)

    def then_result_should_be_none(self):
        assert self.result is None

    async def do_cleanup(self):
        await self.client.close()
        await self._mock_ctx.__aexit__(None, None, None)


class Scenario__find_bot_comment_ignores_system_notes(vedro.Scenario):
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
        self._mock_ctx = mock_gitlab_get_notes(TEST_PROJECT_ID, 42, self.notes_data)
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


class Scenario__add_or_update_pinned_creates_new(vedro.Scenario):
    subject = "add_or_update_pinned_comment creates new when none exists"

    async def given_mock_gitlab_without_existing_comment(self):
        # First mock: no existing notes
        self._notes_mock = mock_gitlab_get_notes(TEST_PROJECT_ID, 42, [])
        await self._notes_mock.__aenter__()
        # Second mock: add comment endpoint
        self._add_mock = mock_gitlab_add_comment(TEST_PROJECT_ID, 42, note_id=999)
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


class Scenario__add_or_update_pinned_updates_existing(vedro.Scenario):
    subject = "add_or_update_pinned_comment updates existing bot comment"

    async def given_mock_gitlab_with_existing_bot_comment(self):
        # Mock: existing bot comment
        notes_data = [
            create_note_response(
                777,
                f"{GitLabClient.BOT_COMMENT_SIGNATURE}\nOld status",
            ),
        ]
        self._notes_mock = mock_gitlab_get_notes(TEST_PROJECT_ID, 42, notes_data)
        await self._notes_mock.__aenter__()
        # Mock: update comment endpoint
        self._update_mock = mock_gitlab_update_comment(TEST_PROJECT_ID, 42, note_id=777)
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


class Scenario__add_or_update_adds_signature_automatically(vedro.Scenario):
    subject = "add_or_update_pinned_comment adds signature if missing"

    async def given_mock_gitlab_without_existing_comment(self):
        self._notes_mock = mock_gitlab_get_notes(TEST_PROJECT_ID, 42, [])
        await self._notes_mock.__aenter__()
        self._add_mock = mock_gitlab_add_comment(TEST_PROJECT_ID, 42, note_id=111)
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
