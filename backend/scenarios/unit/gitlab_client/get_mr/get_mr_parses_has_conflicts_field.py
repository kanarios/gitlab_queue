"""Test scenario: get_mr parses has_conflicts field."""

from __future__ import annotations

import vedro
from scenarios.contexts.gitlab_client_factory import TEST_PROJECT_ID, created_test_client
from scenarios.transports import GitLabMockTransport

from ._helpers import create_mr_api_response


class Scenario(vedro.Scenario):
    subject = "get_mr parses has_conflicts field"

    def given_mock_gitlab_with_conflicting_mr(self):
        self.mr_data = create_mr_api_response(
            iid=50,
            has_conflicts=True,
            merge_status="cannot_be_merged",
        )
        self.transport = GitLabMockTransport()
        self.transport.register_get(
            f"/api/v4/projects/{TEST_PROJECT_ID}/merge_requests/50",
            json_data=self.mr_data,
        )
        self.client = created_test_client(transport=self.transport)

    async def when_get_mr_is_called(self):
        self.result = await self.client.get_mr(50)

    def then_has_conflicts_should_be_true(self):
        assert self.result.has_conflicts is True

    def and_merge_status_should_be_cannot_be_merged(self):
        assert self.result.merge_status == "cannot_be_merged"

    async def do_cleanup(self):
        await self.client.close()
