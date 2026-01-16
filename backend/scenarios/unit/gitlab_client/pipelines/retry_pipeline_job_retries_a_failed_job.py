"""Test scenario: retry_pipeline_job retries a failed job."""

from __future__ import annotations

import vedro
from scenarios.contexts.gitlab_client_factory import TEST_PROJECT_ID, created_test_client
from scenarios.transports import GitLabMockTransport

from ._helpers import create_job_response


class Scenario(vedro.Scenario):
    subject = "retry_pipeline_job retries a failed job"

    def given_mock_gitlab_for_retry(self):
        self.job_data = create_job_response(
            789,
            name="test",
            status="pending",  # After retry, status becomes pending
            stage="test",
        )
        self.transport = GitLabMockTransport()
        self.transport.register_post(
            f"/api/v4/projects/{TEST_PROJECT_ID}/jobs/789/retry",
            json_data=self.job_data,
        )
        self.client = created_test_client(transport=self.transport)

    async def when_retry_pipeline_job_is_called(self):
        self.result = await self.client.retry_pipeline_job(789)

    def then_job_should_be_returned(self):
        assert self.result is not None
        assert self.result.id == 789

    def and_status_should_be_pending(self):
        assert self.result.status == "pending"

    async def do_cleanup(self):
        await self.client.close()
