"""Test scenario: add_or_update_pinned_comment adds signature if missing."""

from __future__ import annotations

import vedro

from gitlab_queue.clients.gitlab import GitLabClient
from scenarios.contexts.gitlab_client_factory import TEST_PROJECT_ID, created_test_client
from scenarios.transports import GitLabMockTransport
from scenarios.transports.responses import note_response


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
        """
        Invoke add_or_update_pinned_comment with a message that lacks the bot signature and store the operation result on self.result.
        """
        self.result = await self.client.add_or_update_pinned_comment(42, "Status without signature")

    def then_note_should_be_created(self):
        """
        Assert that the created merge request note includes the bot signature.

        Fetches the last JSON request payload from the mock transport and verifies that GitLabClient.BOT_COMMENT_SIGNATURE appears in the payload's "body" field.
        """
        request_body = self.transport.get_request_json()
        assert GitLabClient.BOT_COMMENT_SIGNATURE in request_body["body"]

    async def do_cleanup(self):
        """
        Close the scenario's test client and release associated resources.

        Ensures the underlying client connection used by the scenario is closed.
        """
        await self.client.close()
