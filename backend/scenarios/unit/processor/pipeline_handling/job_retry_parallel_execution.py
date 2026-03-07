"""Test job retry executes in parallel for multiple failed jobs.

When two jobs fail, both should be retried via asyncio.gather
(both retry_pipeline_job calls should be awaited).
"""

from __future__ import annotations

import vedro

from scenarios.fakes import create_job

from .._helpers import (
    create_mock_pipeline,
    create_mock_processor,
    create_mock_settings,
    create_mock_state_machine,
    create_processing_context,
)


class Scenario(vedro.Scenario):
    subject = "job retry executes in parallel for multiple failed jobs"

    def given_processor_with_two_failed_jobs(self):
        self.processor = create_mock_processor(settings=create_mock_settings(job_retry_count=1))

        self.pipeline = create_mock_pipeline(pipeline_id=100, sha="abc123", status="failed")

        job_a = create_job(id=10, name="test_a", status="failed")
        job_b = create_job(id=11, name="test_b", status="failed")

        self.processor.gitlab_client.pipeline_jobs_response = [job_a, job_b]

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

    def then_should_continue_is_true(self):
        assert self.should_continue is True

    def and_both_jobs_were_retried(self):
        assert len(self.processor.gitlab_client.retry_job_calls) == 2
        assert set(self.processor.gitlab_client.retry_job_calls) == {10, 11}

    def and_both_jobs_counted_in_retried_jobs(self):
        assert self.updated_retried.get("test_a") == 1
        assert self.updated_retried.get("test_b") == 1
