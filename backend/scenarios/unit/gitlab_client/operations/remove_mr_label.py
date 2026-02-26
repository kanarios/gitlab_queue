"""Test scenario: remove_mr_label removes label and returns updated MR."""

from __future__ import annotations

import vedro

from scenarios.contexts.gitlab_client_factory import TEST_PROJECT_ID, created_test_client
from scenarios.transports import GitLabMockTransport
from scenarios.transports.responses import mr_response


class Scenario(vedro.Scenario):
    subject = "remove_mr_label removes label and returns updated MR"

    def given_mock_gitlab_with_label_removal(self):
        """
        Configure a mock GitLab environment and test client for a merge request label-removal scenario.

        Creates MR response data with iid 42 and an empty labels list, registers a PUT handler on the mock transport for
        "/api/v4/projects/{TEST_PROJECT_ID}/merge_requests/42" that returns the prepared MR JSON, and constructs a test client
        that uses this transport.
        """
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
        """
        Invoke the GitLab client's remove_mr_label for merge request iid 42 with label "merge_queue" and store the returned merge request on self.result.

        The operation calls the client's remove_mr_label(42, "merge_queue") and saves its result to the scenario's self.result for later assertions.
        """
        self.result = await self.client.remove_mr_label(42, "merge_queue")

    def then_result_should_be_merge_request(self):
        """
        Verify that the operation returned a merge request with iid 42.

        Asserts that the stored result is not None and that its `iid` equals 42.
        """
        assert self.result is not None
        assert self.result.iid == 42

    def and_labels_should_be_empty(self):
        """
        Assert that the stored merge request's labels list is empty.

        Raises:
            AssertionError: If the merge request's labels list is not empty.
        """
        assert self.result.labels == []

    def and_request_body_should_contain_remove_labels(self):
        """
        Asserts that the last transport request JSON contains the expected remove_labels payload.

        Raises:
            AssertionError: If the `remove_labels` field is not equal to "merge_queue".
        """
        request_json = self.transport.get_request_json()
        assert request_json["remove_labels"] == "merge_queue"

    async def do_cleanup(self):
        """
        Close the scenario's test client and release related resources.

        This coroutine closes the GitLab test client created for the scenario; call it during teardown.
        """
        await self.client.close()
