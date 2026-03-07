"""Test pipeline failed with all canceled jobs removes MR with clear error message.

When a pipeline fails and all jobs are in "canceled" status (not "failed"),
the processor should trigger pipeline_failed with an error message that
explicitly mentions "canceled" — not the generic "no retryable jobs found".
"""

from __future__ import annotations

import vedro

from scenarios.fakes import create_job

from .._helpers import (
    create_mock_pipeline,
    create_mock_processor,
    create_mock_state_machine,
    create_processing_context,
)


class Scenario(vedro.Scenario):
    subject = "pipeline failed with all canceled jobs removes MR with clear message"

    def given_processor_with_all_canceled_jobs(self):
        self.processor = create_mock_processor()
        self.pipeline = create_mock_pipeline(pipeline_id=100, sha="abc123", status="failed")

        canceled_job = create_job(id=10, name="unit_tests", status="canceled")
        self.processor.gitlab_client.pipeline_jobs_response = [canceled_job]

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

    def and_new_start_time_is_none(self):
        assert self.new_start_time is None

    def and_trigger_pipeline_failed_was_called(self):
        assert len(self.mock_sm.pipeline_failed_calls) == 1

    def and_error_message_mentions_canceled(self):
        call = self.mock_sm.pipeline_failed_calls[0]
        assert "canceled" in call["error_message"].lower()

    def and_updated_retried_is_unchanged(self):
        assert self.updated_retried == self.retried_jobs
