"""Test job-level retry succeeds on first attempt.

When a pipeline fails, retried_jobs is empty, and job_retry_count=1,
the processor should retry the failed job and return should_continue=True.
trigger_pipeline_failed should NOT be called.
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
    subject = "job retry succeeds on first attempt - retries job, does not remove MR"

    def given_processor_with_one_failed_job_and_no_prior_retries(self):
        self.processor = create_mock_processor(settings=create_mock_settings(job_retry_count=1))

        self.pipeline = create_mock_pipeline(pipeline_id=100, sha="abc123", status="failed")

        failed_job = create_job(id=10, name="unit_tests", status="failed")
        self.processor.gitlab_client.pipeline_jobs_response = [failed_job]

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

    def and_new_start_time_is_set(self):
        assert self.new_start_time is not None

    def and_trigger_pipeline_failed_is_not_called(self):
        assert len(self.mock_sm.pipeline_failed_calls) == 0

    def and_retry_pipeline_job_was_called(self):
        assert self.processor.gitlab_client.retry_job_calls == [10]

    def and_retried_jobs_updated(self):
        assert self.updated_retried.get("unit_tests") == 1

    def and_notify_job_retry_called(self):
        assert len(self.mock_sm.job_retry_calls) == 1
