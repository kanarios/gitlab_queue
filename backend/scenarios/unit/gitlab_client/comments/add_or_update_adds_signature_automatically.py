"""Test scenario: add_or_update_pinned_comment adds signature if missing."""

from __future__ import annotations

import vedro
from scenarios.contexts.gitlab_client_factory import TEST_PROJECT_ID, created_test_client
from scenarios.transports import GitLabMockTransport
from scenarios.transports.responses import note_response

from gitlab_queue.clients.gitlab import GitLabClient


class Scenario(vedro.Scenario):
    subject = "add_or_update_pinned_comment adds signature if missing"

    def given_mock_gitlab_without_existing_comment(self):
        self.transport = GitLabMockTransport()
        self.transport.register_get(
            f"/api/v4/projects/{TEST_PROJECT_ID}/merge_requests/42/notes",
            json_data=[],
        )
        self.transport.register_post(
            f"/api/v4/projects/{TEST_PROJECT_ID}/merge_requests/42/notes",
            json_data=note_response(note_id=111, body="Status without signature"),
        )
        self.client = created_test_client(transport=self.transport)

    async def when_add_or_update_is_called_without_signature(self):
        # Body doesn't contain signature - should be added automatically
        self.result = await self.client.add_or_update_pinned_comment(42, "Status without signature")

    def then_note_should_be_created(self):
        request_body = self.transport.get_request_json()
        assert GitLabClient.BOT_COMMENT_SIGNATURE in request_body["body"]

    async def do_cleanup(self):
        await self.client.close()
