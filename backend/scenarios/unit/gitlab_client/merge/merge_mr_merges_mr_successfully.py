"""Test scenario: merge_mr merges MR successfully."""

from __future__ import annotations

import vedro

from scenarios.contexts.gitlab_client_factory import TEST_PROJECT_ID, created_test_client
from scenarios.transports import GitLabMockTransport

from ._helpers import create_mr_response


class Scenario(vedro.Scenario):
    subject = "merge_mr merges MR successfully"

    def given_mock_gitlab_with_mergeable_mr(self):
        # First call: get_mr to check merge_status
        mr_data = create_mr_response(iid=42, merge_status="can_be_merged")
        # Second call: merge endpoint returns merged MR
        merged_data = create_mr_response(iid=42, state="merged", merge_status="merged")

        self.transport = GitLabMockTransport()
        self.transport.register_get(
            f"/api/v4/projects/{TEST_PROJECT_ID}/merge_requests/42",
            json_data=mr_data,
        )
        self.transport.register_put(
            f"/api/v4/projects/{TEST_PROJECT_ID}/merge_requests/42/merge",
            json_data=merged_data,
        )
        self.client = created_test_client(transport=self.transport)

    async def when_merge_mr_is_called(self):
        self.result = await self.client.merge_mr(42)

    def then_result_should_be_merged_mr(self):
        assert self.result is not None
        assert self.result.iid == 42

    def and_state_should_be_merged(self):
        assert self.result.state == "merged"

    async def do_cleanup(self):
        await self.client.close()
