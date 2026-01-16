"""Test scenario: list_mrs_with_label accepts state parameter."""

from __future__ import annotations

import vedro
from scenarios.contexts.gitlab_client_factory import TEST_PROJECT_ID, created_test_client
from scenarios.transports import GitLabMockTransport

from ._helpers import create_mr_api_response


class Scenario(vedro.Scenario):
    subject = "list_mrs_with_label accepts state parameter"

    def given_mock_gitlab_with_closed_mr(self):
        self.mrs_data = [
            create_mr_api_response(iid=1, state="closed"),
        ]
        self.transport = GitLabMockTransport()
        self.transport.register_get(
            f"/api/v4/projects/{TEST_PROJECT_ID}/merge_requests",
            json_data=self.mrs_data,
        )
        self.client = created_test_client(transport=self.transport)

    async def when_list_mrs_is_called_with_state(self):
        # Note: The mock doesn't verify state param, but we verify the method accepts it
        self.result = await self.client.list_mrs_with_label("merge_queue", state="closed")

    def then_result_should_contain_closed_mr(self):
        assert len(self.result) == 1
        assert self.result[0].state == "closed"

    async def do_cleanup(self):
        await self.client.close()
