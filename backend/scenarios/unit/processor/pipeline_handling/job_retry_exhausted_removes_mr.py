"""Test job retry exhausted removes MR from queue.

When a pipeline fails and job has already been retried the maximum number
of times, the processor should trigger pipeline_failed and NOT call retry_pipeline_job.
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
    subject = "job retry exhausted removes MR from queue"

    def given_processor_with_exhausted_job_retries(self):
        self.processor = create_mock_processor(settings=create_mock_settings(job_retry_count=1))

        self.pipeline = create_mock_pipeline(pipeline_id=100, sha="abc123", status="failed")

        failed_job = create_job(id=10, name="unit_tests", status="failed")
        self.processor.gitlab_client.pipeline_jobs_response = [failed_job]

        self.mock_sm = create_mock_state_machine()
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.mock_sm)

        # unit_tests already retried once = at limit (job_retry_count=1)
        self.retried_jobs = {"unit_tests": 1}

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

    def and_new_start_time_is_none(self):
        assert self.new_start_time is None

    def and_trigger_pipeline_failed_was_called(self):
        assert len(self.mock_sm.pipeline_failed_calls) == 1
        call = self.mock_sm.pipeline_failed_calls[0]
        assert "unit_tests" in call["failed_jobs"]

    def and_retry_pipeline_job_not_called(self):
        assert len(self.processor.gitlab_client.retry_job_calls) == 0
