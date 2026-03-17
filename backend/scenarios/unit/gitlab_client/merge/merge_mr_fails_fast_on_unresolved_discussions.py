"""Test: merge_mr fails fast when detailed_merge_status is discussions_not_resolved.

When GitLab merge API returns 405 and the MR has unresolved discussions,
the client should raise GitLabConflictError immediately instead of retrying.
"""

from __future__ import annotations

import vedro

from gitlab_queue.clients.gitlab import GitLabConflictError
from scenarios.contexts.gitlab_client_factory import TEST_PROJECT_ID, created_test_client
from scenarios.transports import GitLabMockTransport

from ._helpers import create_mr_response


class Scenario(vedro.Scenario):
    subject = "merge_mr fails fast when discussions are not resolved"

    def given_mr_with_unresolved_discussions(self):
        mr_data = create_mr_response(
            iid=42,
            merge_status="can_be_merged",
            detailed_merge_status="discussions_not_resolved",
        )
        self.transport = GitLabMockTransport()
        self.transport.register_get(
            f"/api/v4/projects/{TEST_PROJECT_ID}/merge_requests/42",
            json_data=mr_data,
        )
        # Merge endpoint returns 405 (unresolved discussions block merge)
        self.transport.register_put(
            f"/api/v4/projects/{TEST_PROJECT_ID}/merge_requests/42/merge",
            status=405,
            json_data={"message": "405 Method Not Allowed"},
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

    def then_error_message_should_mention_discussions(self):
        assert "unresolved discussions" in str(self.error)

    def then_only_one_merge_attempt_was_made(self):
        # Should fail fast: 1 GET (get_mr) + 1 PUT (merge attempt)
        put_requests = [r for r in self.transport.history if r.method == "PUT"]
        assert len(put_requests) == 1

    async def do_cleanup(self):
        await self.client.close()
