"""Test: merge_mr retries on 405 when detailed_merge_status is not a known block reason.

When GitLab merge API returns 405 but detailed_merge_status is None or unknown,
the client should retry as before (regression test for existing behavior).
"""

from __future__ import annotations

import vedro

from gitlab_queue.clients.gitlab import GitLabClient, GitLabConflictError
from scenarios.contexts.gitlab_client_factory import TEST_PROJECT_ID, created_test_settings
from scenarios.transports import GitLabMockTransport

from ._helpers import create_mr_response

MERGE_STATUS_RETRY_MAX = 3


class Scenario(vedro.Scenario):
    subject = "merge_mr retries on 405 when detailed_merge_status is unknown"

    def given_mr_with_unknown_detailed_status(self):
        mr_data = create_mr_response(
            iid=42,
            merge_status="can_be_merged",
            # No detailed_merge_status → retryable
        )
        self.transport = GitLabMockTransport()
        self.transport.register_get(
            f"/api/v4/projects/{TEST_PROJECT_ID}/merge_requests/42",
            json_data=mr_data,
        )
        self.transport.register_put(
            f"/api/v4/projects/{TEST_PROJECT_ID}/merge_requests/42/merge",
            status=405,
            json_data={"message": "405 Method Not Allowed"},
        )
        settings = created_test_settings()
        settings.merge_status_retry_max = MERGE_STATUS_RETRY_MAX
        settings.merge_status_retry_delay_seconds = 0.01
        self.client = GitLabClient(settings, transport=self.transport)

    async def when_merge_mr_is_called(self):
        self.error = None
        try:
            await self.client.merge_mr(42)
        except GitLabConflictError as e:
            self.error = e

    def then_error_should_be_raised(self):
        assert self.error is not None

    def then_multiple_merge_attempts_were_made(self):
        put_requests = [r for r in self.transport.history if r.method == "PUT"]
        assert len(put_requests) == MERGE_STATUS_RETRY_MAX

    async def do_cleanup(self):
        await self.client.close()
