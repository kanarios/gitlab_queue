"""Test job_retry_count=0 removes MR immediately without retry.

When job_retry_count=0, no retries are allowed. MR should be removed
immediately on first failure without calling retry_pipeline_job.
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
    subject = "job_retry_count=0 removes MR immediately without retry"

    def given_processor_with_zero_retry_count(self):
        self.processor = create_mock_processor(settings=create_mock_settings(job_retry_count=0))

        self.pipeline = create_mock_pipeline(pipeline_id=100, sha="abc123", status="failed")

        failed_job = create_job(id=10, name="unit_tests", status="failed")
        self.processor.gitlab_client.pipeline_jobs_response = [failed_job]

        self.mock_sm = create_mock_state_machine()
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.mock_sm)

        # No prior retries — but limit is 0
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

    def and_new_start_time_is_none(self):
        assert self.new_start_time is None

    def and_updated_retried_is_empty(self):
        assert self.updated_retried == {}

    def and_trigger_pipeline_failed_was_called(self):
        assert len(self.mock_sm.pipeline_failed_calls) == 1
        call = self.mock_sm.pipeline_failed_calls[0]
        assert call["failed_jobs"] == ["unit_tests"]
        assert call["retried_jobs"] == {}

    def and_retry_pipeline_job_was_not_called(self):
        assert len(self.processor.gitlab_client.retry_job_calls) == 0
