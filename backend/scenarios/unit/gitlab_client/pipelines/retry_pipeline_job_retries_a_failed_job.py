"""Test scenario: retry_pipeline_job retries a failed job."""

from __future__ import annotations

import vedro
from scenarios.contexts.gitlab_client_factory import TEST_PROJECT_ID, create_test_client
from scenarios.contexts.jj_gitlab_mock import mocked_gitlab_retry_job

from ._helpers import create_job_response


class Scenario(vedro.Scenario):
    subject = "retry_pipeline_job retries a failed job"

    async def given_mock_gitlab_for_retry(self):
        self.job_data = create_job_response(
            789,
            name="test",
            status="pending",  # After retry, status becomes pending
            stage="test",
        )
        self._mock_ctx = mocked_gitlab_retry_job(TEST_PROJECT_ID, 789, self.job_data)
        await self._mock_ctx.__aenter__()
        self.client = create_test_client()

    async def when_retry_pipeline_job_is_called(self):
        self.result = await self.client.retry_pipeline_job(789)

    def then_job_should_be_returned(self):
        assert self.result is not None
        assert self.result.id == 789

    def and_status_should_be_pending(self):
        assert self.result.status == "pending"

    async def do_cleanup(self):
        await self.client.close()
        await self._mock_ctx.__aexit__(None, None, None)
