"""Test _handle_pipeline_failure_retry triggers pipeline_failed when no failed jobs found.

Lines 738-749: when pipeline failed but jobs have non-failed/non-active/non-canceled statuses,
trigger_pipeline_failed and return (False, None, retried_jobs).
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
    subject = "handle pipeline failure retry removes MR when no failed jobs in any retryable status"

    def given_processor_with_pipeline_failed_and_no_retryable_jobs(self):
        self.processor = create_mock_processor(settings=create_mock_settings(job_retry_count=2))
        self.pipeline = create_mock_pipeline(pipeline_id=100, sha="abc123", status="failed")

        # Jobs exist but none are 'failed', 'running', 'pending', 'created', or 'canceled'
        # (e.g., all 'success' — unexpected but possible race condition)
        succeeded_job = create_job(id=10, name="unit_tests", status="success")
        self.processor.gitlab_client.pipeline_jobs_response = [succeeded_job]

        self.mock_sm = create_mock_state_machine()
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.mock_sm)

    async def when_handle_pipeline_failure_retry_is_called(self):
        (
            self.should_continue,
            self.new_start,
            self.updated_retried,
        ) = await self.processor._pipeline_handler.handle_pipeline_failure_retry(
            ctx=self.ctx,
            pipeline=self.pipeline,
            retried_jobs={},
        )

    def then_should_continue_is_false(self):
        assert self.should_continue is False

    def and_trigger_pipeline_failed_was_called(self):
        assert len(self.mock_sm.pipeline_failed_calls) == 1

    def and_new_start_is_none(self):
        assert self.new_start is None
