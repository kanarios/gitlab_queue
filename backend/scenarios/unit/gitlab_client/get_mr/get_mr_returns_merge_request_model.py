"""Test scenario: get_mr returns MergeRequest model."""

from __future__ import annotations

import vedro
from scenarios.contexts.gitlab_client_factory import TEST_PROJECT_ID, created_test_client
from scenarios.transports import GitLabMockTransport

from ._helpers import create_mr_api_response


class Scenario(vedro.Scenario):
    subject = "get_mr returns MergeRequest model"

    def given_mock_gitlab_with_mr(self):
        self.mr_data = create_mr_api_response(iid=42, title="Test MR")
        self.transport = GitLabMockTransport()
        self.transport.register_get(
            f"/api/v4/projects/{TEST_PROJECT_ID}/merge_requests/42",
            json_data=self.mr_data,
        )
        self.client = created_test_client(transport=self.transport)

    async def when_get_mr_is_called(self):
        self.result = await self.client.get_mr(42)

    def then_result_should_be_merge_request(self):
        assert self.result is not None

    def and_iid_should_match(self):
        assert self.result.iid == 42

    def and_title_should_match(self):
        assert self.result.title == "Test MR"

    def and_state_should_match(self):
        assert self.result.state == "opened"

    def and_author_should_be_parsed(self):
        assert self.result.author.id == 1
        assert self.result.author.name == "Test User"
        assert self.result.author.username == "testuser"

    async def do_cleanup(self):
        if hasattr(self, "client"):
            await self.client.close()
