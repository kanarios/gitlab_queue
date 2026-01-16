"""Test scenario: add_or_update_pinned_comment creates new when none exists."""

from __future__ import annotations

import vedro
from scenarios.contexts.gitlab_client_factory import TEST_PROJECT_ID, created_test_client
from scenarios.transports import GitLabMockTransport
from scenarios.transports.responses import note_response


class Scenario(vedro.Scenario):
    subject = "add_or_update_pinned_comment creates new when none exists"

    def given_mock_gitlab_without_existing_comment(self):
        self.transport = GitLabMockTransport()
        # First: no existing notes
        self.transport.register_get(
            f"/api/v4/projects/{TEST_PROJECT_ID}/merge_requests/42/notes",
            json_data=[],
        )
        # Second: add comment endpoint
        self.transport.register_post(
            f"/api/v4/projects/{TEST_PROJECT_ID}/merge_requests/42/notes",
            json_data=note_response(note_id=999, body="Status update"),
        )
        self.client = created_test_client(transport=self.transport)

    async def when_add_or_update_is_called(self):
        self.result = await self.client.add_or_update_pinned_comment(42, "Status update")

    def then_note_should_be_created(self):
        assert self.result is not None

    def and_note_id_should_be_returned(self):
        assert self.result.id == 999

    async def do_cleanup(self):
        await self.client.close()
