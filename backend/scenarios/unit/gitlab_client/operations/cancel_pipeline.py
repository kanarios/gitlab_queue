"""Test scenario: cancel_pipeline returns cancelled pipeline."""

from __future__ import annotations

import vedro

from scenarios.contexts.gitlab_client_factory import TEST_PROJECT_ID, created_test_client
from scenarios.transports import GitLabMockTransport
from scenarios.transports.responses import pipeline_response


class Scenario(vedro.Scenario):
    subject = "cancel_pipeline returns cancelled pipeline"

    def given_mock_gitlab_with_pipeline_cancel(self):
        """
        Set up a mocked GitLab transport and test client that return a canceled pipeline for pipeline id 100.

        Creates pipeline data with id 100, status "canceled", sha "abc123def456", and ref "main"; registers a POST mock for /api/v4/projects/{TEST_PROJECT_ID}/pipelines/100/cancel that returns this data; and constructs a test client using the mock transport.
        """
        self.pipeline_data = pipeline_response(
            100,
            status="canceled",
            sha="abc123def456",
            ref="main",
        )
        self.transport = GitLabMockTransport()
        self.transport.register_post(
            f"/api/v4/projects/{TEST_PROJECT_ID}/pipelines/100/cancel",
            json_data=self.pipeline_data,
        )
        self.client = created_test_client(transport=self.transport)

    async def when_cancel_pipeline_is_called(self):
        """
        Call the client's cancel_pipeline for pipeline id 100 and store the response on self.result.

        This step invokes the cancellation API and saves the returned pipeline object to the scenario's
        self.result attribute for later assertions.
        """
        self.result = await self.client.cancel_pipeline(100)

    def then_pipeline_should_be_returned(self):
        """
        Asserts that a pipeline result was returned and its id equals 100.

        Raises:
            AssertionError: If no pipeline result is present or the result's `id` is not 100.
        """
        assert self.result is not None
        assert self.result.id == 100

    def and_status_should_be_canceled(self):
        """
        Assert that the retrieved pipeline has status "canceled".

        Raises:
            AssertionError: If the pipeline's status is not "canceled".
        """
        assert self.result.status == "canceled"

    def and_sha_should_match(self):
        """
        Asserts that the returned pipeline's SHA equals "abc123def456".
        """
        assert self.result.sha == "abc123def456"

    async def do_cleanup(self):
        """
        Close the test client and release its resources.

        Closes the scenario's HTTP client connection established for testing.
        """
        await self.client.close()
