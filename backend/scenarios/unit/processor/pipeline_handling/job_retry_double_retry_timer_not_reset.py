"""Test that double retry protection does NOT reset the timer.

When pipeline=failed but jobs are already running (race condition after retry),
new_start_time must be None so the polling timeout can still fire.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import vedro

from .._helpers import (
    create_mock_pipeline,
    create_mock_processor,
    create_mock_state_machine,
    create_processing_context,
)


class Scenario(vedro.Scenario):
    subject = "double retry protection returns None new_start_time to preserve timeout"

    def given_pipeline_failed_but_jobs_running(self):
        self.processor = create_mock_processor()
        self.processor.settings.job_retry_count = 1
        self.pipeline = create_mock_pipeline(pipeline_id=100, sha="abc123", status="failed")

        running_job = MagicMock()
        running_job.id = 10
        running_job.name = "unit_tests"
        running_job.status = "running"

        self.processor.gitlab_client.get_pipeline_jobs = AsyncMock(return_value=[running_job])
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
        self.processor.gitlab_client.retry_pipeline_job.assert_not_called()

    def and_pipeline_failed_was_not_triggered(self):
        self.mock_sm.trigger_pipeline_failed.assert_not_awaited()
