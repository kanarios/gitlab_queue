"""Test scenario: remove_mr_label removes label and returns updated MR."""

from __future__ import annotations

import vedro
from scenarios.contexts.gitlab_client_factory import TEST_PROJECT_ID, created_test_client
from scenarios.transports import GitLabMockTransport
from scenarios.transports.responses import mr_response


class Scenario(vedro.Scenario):
    subject = "remove_mr_label removes label and returns updated MR"

    def given_mock_gitlab_with_label_removal(self):
        self.mr_data = mr_response(
            iid=42,
            labels=[],
        )
        self.transport = GitLabMockTransport()
        self.transport.register_put(
            f"/api/v4/projects/{TEST_PROJECT_ID}/merge_requests/42",
            json_data=self.mr_data,
        )
        self.client = created_test_client(transport=self.transport)

    async def when_remove_mr_label_is_called(self):
        self.result = await self.client.remove_mr_label(42, "merge_queue")

    def then_result_should_be_merge_request(self):
        assert self.result is not None
        assert self.result.iid == 42

    def and_labels_should_be_empty(self):
        assert self.result.labels == []

    def and_request_body_should_contain_remove_labels(self):
        request_json = self.transport.get_request_json()
        assert request_json["remove_labels"] == "merge_queue"

    async def do_cleanup(self):
        if hasattr(self, "client"):
            await self.client.close()
