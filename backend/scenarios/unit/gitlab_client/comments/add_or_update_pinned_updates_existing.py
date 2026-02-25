"""Test scenario: add_or_update_pinned_comment updates existing bot comment."""

from __future__ import annotations

import vedro
from scenarios.contexts.gitlab_client_factory import TEST_PROJECT_ID, created_test_client
from scenarios.transports import GitLabMockTransport
from scenarios.transports.responses import note_response

from gitlab_queue.clients.gitlab import GitLabClient

from ._helpers import create_note_response as create_note_data


class Scenario(vedro.Scenario):
    subject = "add_or_update_pinned_comment updates existing bot comment"

    def given_mock_gitlab_with_existing_bot_comment(self):
        self.transport = GitLabMockTransport()
        # Mock: existing bot comment
        notes_data = [
            create_note_data(
                777,
                f"{GitLabClient.BOT_COMMENT_SIGNATURE}\nOld status",
            ),
        ]
        self.transport.register_get(
            f"/api/v4/projects/{TEST_PROJECT_ID}/merge_requests/42/notes",
            json_data=notes_data,
        )
        # Mock: update comment endpoint
        self.transport.register_put(
            f"/api/v4/projects/{TEST_PROJECT_ID}/merge_requests/42/notes/777",
            json_data=note_response(note_id=777, body="New status"),
        )
        self.client = created_test_client(transport=self.transport)

    async def when_add_or_update_is_called(self):
        self.result = await self.client.add_or_update_pinned_comment(42, "New status")

    def then_note_should_be_updated(self):
        assert self.result is not None

    def and_note_id_should_match_existing(self):
        assert self.result.id == 777

    async def do_cleanup(self):
        await self.client.close()
