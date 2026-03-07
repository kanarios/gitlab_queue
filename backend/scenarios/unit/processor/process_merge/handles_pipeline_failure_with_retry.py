"""Test _handle_pipeline_failure_retry when retry count is at maximum.

When a pipeline fails and retry_count >= max_retries, the processor must
trigger pipeline_failed on the state machine and signal the caller to stop
retrying (should_continue=False).

Covers _handle_pipeline_failure_retry: the exhausted-retry branch that calls
trigger_pipeline_failed and returns (False, None).
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
    subject = "handle pipeline failure retry triggers pipeline failed when max retries exhausted"

    def given_processor_with_failed_pipeline_and_no_retries_left(self):
        self.processor = create_mock_processor()

        self.pipeline = create_mock_pipeline(pipeline_id=100, sha="abc123", status="failed")

        # Set up jobs that have already been retried to the max (job_retry_count=1 by default)
        self.processor.gitlab_client.pipeline_jobs_response = [
            create_job(id=1, name="unit_tests", status="failed"),
            create_job(id=2, name="lint", status="failed"),
        ]

        self.mock_sm = create_mock_state_machine()
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.mock_sm)

        # Jobs already retried once (matches job_retry_count=1 default) → exhausted
        self.retried_jobs = {"unit_tests": 1, "lint": 1}

    async def when_handle_pipeline_failure_retry_is_called(self):
        (
            self.should_continue,
            self.new_start_time,
            self.updated_retried,
        ) = await self.processor._handle_pipeline_failure_retry(
            ctx=self.ctx,
            pipeline=self.pipeline,
            retried_jobs=self.retried_jobs,
        )

    def then_should_continue_is_false(self):
        assert self.should_continue is False

    def and_new_start_time_is_none(self):
        assert self.new_start_time is None

    def and_pipeline_failed_is_triggered_on_state_machine(self):
        assert len(self.mock_sm.pipeline_failed_calls) == 1
        call_kwargs = self.mock_sm.pipeline_failed_calls[0]
        assert {"unit_tests", "lint"} <= set(call_kwargs["failed_jobs"])

    def and_rebase_is_not_attempted(self):
        assert self.processor.gitlab_client.rebase_calls == []
