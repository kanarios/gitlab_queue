"""Test scenario: list_mrs_with_label parses MR fields correctly."""

from __future__ import annotations

import vedro
from scenarios.contexts.gitlab_client_factory import TEST_PROJECT_ID, created_test_client
from scenarios.transports import GitLabMockTransport

from ._helpers import create_mr_api_response


class Scenario(vedro.Scenario):
    subject = "list_mrs_with_label parses MR fields correctly"

    def given_mock_gitlab_with_detailed_mr(self):
        self.mrs_data = [
            create_mr_api_response(
                iid=42,
                title="Detailed MR",
                state="opened",
                labels=["merge_queue", "feature"],
            ),
        ]
        self.transport = GitLabMockTransport()
        self.transport.register_get(
            f"/api/v4/projects/{TEST_PROJECT_ID}/merge_requests",
            json_data=self.mrs_data,
        )
        self.client = created_test_client(transport=self.transport)

    async def when_list_mrs_is_called(self):
        self.result = await self.client.list_mrs_with_label("merge_queue")

    def then_mr_fields_should_be_parsed(self):
        mr = self.result[0]
        assert mr.iid == 42
        assert mr.title == "Detailed MR"
        assert mr.state == "opened"
        assert mr.labels == ["merge_queue", "feature"]
        assert mr.source_branch == "feature-42"
        assert mr.target_branch == "master"

    def and_author_should_be_parsed(self):
        mr = self.result[0]
        assert mr.author.id == 42
        assert mr.author.username == "user42"

    async def do_cleanup(self):
        await self.client.close()
