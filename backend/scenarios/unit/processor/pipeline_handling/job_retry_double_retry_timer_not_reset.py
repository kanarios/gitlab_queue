"""Test that double retry protection does NOT reset the timer.

When pipeline=failed but jobs are already running (race condition after retry),
new_start_time must be None so the polling timeout can still fire.
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
    subject = "double retry protection returns None new_start_time to preserve timeout"

    def given_pipeline_failed_but_jobs_running(self):
        self.processor = create_mock_processor(settings=create_mock_settings(job_retry_count=1))
        self.pipeline = create_mock_pipeline(pipeline_id=100, sha="abc123", status="failed")

        running_job = create_job(id=10, name="unit_tests", status="running")
        self.processor.gitlab_client.pipeline_jobs_response = [running_job]

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

    def and_new_start_time_is_none(self):
        assert self.new_start_time is None, f"Expected None (timer must not reset) but got {self.new_start_time}"

    def and_no_retry_api_call_was_made(self):
        assert len(self.processor.gitlab_client.retry_job_calls) == 0

    def and_pipeline_failed_was_not_triggered(self):
        assert len(self.mock_sm.pipeline_failed_calls) == 0
