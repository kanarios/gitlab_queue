"""Test scenario: merge_mr returns MR with merged state."""

from __future__ import annotations

import vedro

from scenarios.contexts.gitlab_client_factory import TEST_PROJECT_ID, created_test_client
from scenarios.transports import GitLabMockTransport

from ._helpers import create_mr_response


class Scenario(vedro.Scenario):
    subject = "merge_mr returns MR with merged state"

    def given_mock_gitlab_for_successful_merge(self):
        # Check merge status
        mr_data = create_mr_response(iid=99, merge_status="can_be_merged")
        # Merge returns merged MR
        merged_data = create_mr_response(
            iid=99,
            state="merged",
            merge_status="merged",
        )

        self.transport = GitLabMockTransport()
        self.transport.register_get(
            f"/api/v4/projects/{TEST_PROJECT_ID}/merge_requests/99",
            json_data=mr_data,
        )
        self.transport.register_put(
            f"/api/v4/projects/{TEST_PROJECT_ID}/merge_requests/99/merge",
            json_data=merged_data,
        )
        self.client = created_test_client(transport=self.transport)

    async def when_merge_mr_is_called(self):
        self.result = await self.client.merge_mr(99)

    def then_iid_should_match(self):
        assert self.result.iid == 99

    def and_state_should_be_merged(self):
        assert self.result.state == "merged"

    def and_merge_status_should_be_merged(self):
        assert self.result.merge_status == "merged"

    async def do_cleanup(self):
        await self.client.close()
