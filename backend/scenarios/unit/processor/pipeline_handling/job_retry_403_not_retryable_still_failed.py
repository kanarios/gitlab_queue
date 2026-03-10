"""Test 403 'not retryable' still fails when job remains failed.

When retry_pipeline_job returns 403 but the same-named job is still in
'failed' status (not retried by anyone), the handler should fail the
pipeline as usual.
"""

from __future__ import annotations

import vedro

from gitlab_queue.clients.gitlab import GitLabAPIError
from scenarios.fakes import create_job

from .._helpers import (
    create_mock_pipeline,
    create_mock_processor,
    create_mock_settings,
    create_mock_state_machine,
    create_processing_context,
)


class Scenario(vedro.Scenario):
    subject = "job retry 403 fails when job still in failed status"

    def given_processor_with_403_error_and_still_failed_job(self):
        self.processor = create_mock_processor(settings=create_mock_settings(job_retry_count=1))

        self.pipeline = create_mock_pipeline(pipeline_id=100, sha="abc123", status="failed")

        failed_job = create_job(id=10, name="e2e-tests", status="failed")

        # Both calls return the same failed job — nobody retried it
        self.processor.gitlab_client.pipeline_jobs_response_sequence = [
            [failed_job],
            [failed_job],
        ]

        self.processor.gitlab_client.retry_job_error = GitLabAPIError("Job is not retryable", status_code=403)

        self.mock_sm = create_mock_state_machine()
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.mock_sm)
        self.retried_jobs: dict[str, int] = {}

    async def when_handle_pipeline_failure_retry_is_called(self):
        (
            self.should_continue,
            self.new_start_time,
            self.updated_retried,
        ) = await self.processor._pipeline_handler.handle_pipeline_failure_retry(
            ctx=self.ctx,
            pipeline=self.pipeline,
            retried_jobs=self.retried_jobs,
        )

    def then_should_continue_is_false(self):
        assert self.should_continue is False

    def and_trigger_pipeline_failed_was_called(self):
        assert len(self.mock_sm.pipeline_failed_calls) == 1
        call = self.mock_sm.pipeline_failed_calls[0]
        assert "e2e-tests" in call["failed_jobs"]
