"""Test scenario: get_mr parses all MR fields correctly."""

from __future__ import annotations

import vedro

from scenarios.contexts.gitlab_client_factory import TEST_PROJECT_ID, created_test_client
from scenarios.transports import GitLabMockTransport

from ._helpers import create_mr_api_response


class Scenario(vedro.Scenario):
    subject = "get_mr parses all MR fields correctly"

    def given_mock_gitlab_with_full_mr(self):
        self.mr_data = create_mr_api_response(
            iid=99,
            title="Full MR Test",
            state="merged",
            labels=["bug", "critical"],
            sha="full123sha",
            source_branch="hotfix",
            target_branch="main",
            merge_status="merged",
            has_conflicts=False,
            rebase_in_progress=False,
        )
        self.transport = GitLabMockTransport()
        self.transport.register_get(
            f"/api/v4/projects/{TEST_PROJECT_ID}/merge_requests/99",
            json_data=self.mr_data,
        )
        self.client = created_test_client(transport=self.transport)

    async def when_get_mr_is_called(self):
        self.result = await self.client.get_mr(99)

    def then_sha_should_match(self):
        assert self.result.sha == "full123sha"

    def and_source_branch_should_match(self):
        assert self.result.source_branch == "hotfix"

    def and_target_branch_should_match(self):
        assert self.result.target_branch == "main"

    def and_merge_status_should_match(self):
        assert self.result.merge_status == "merged"

    def and_labels_should_match(self):
        assert self.result.labels == ["bug", "critical"]

    def and_has_conflicts_should_be_false(self):
        assert self.result.has_conflicts is False

    def and_rebase_in_progress_should_be_false(self):
        assert self.result.rebase_in_progress is False

    async def do_cleanup(self):
        await self.client.close()
