"""Test scenario: merge_mr raises GitLabConflictError when merge_status is unchecked."""

from __future__ import annotations

import vedro
from scenarios.contexts.gitlab_client_factory import TEST_PROJECT_ID, created_test_client
from scenarios.transports import GitLabMockTransport

from gitlab_queue.clients.gitlab import GitLabConflictError

from ._helpers import create_mr_response


class Scenario(vedro.Scenario):
    subject = "try to merge mr when merge status is unchecked"

    def given_mock_gitlab_with_unchecked_mr(self):
        # MR merge status not yet determined
        mr_data = create_mr_response(
            iid=42,
            merge_status="unchecked",
        )
        self.transport = GitLabMockTransport()
        self.transport.register_get(
            f"/api/v4/projects/{TEST_PROJECT_ID}/merge_requests/42",
            json_data=mr_data,
        )
        self.client = created_test_client(transport=self.transport)

    async def when_merge_mr_is_called(self):
        self.error = None
        try:
            await self.client.merge_mr(42)
        except GitLabConflictError as e:
            self.error = e

    def then_error_should_be_raised(self):
        assert self.error is not None

    def and_error_message_should_mention_unchecked(self):
        assert "unchecked" in str(self.error)

    async def do_cleanup(self):
        await self.client.close()
