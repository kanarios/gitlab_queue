"""Test _handle_pipeline_failure_retry when job retry count is exhausted.

When a pipeline fails and all jobs have already been retried the maximum
number of times, the processor must trigger pipeline_failed on the state
machine and signal the caller to stop retrying.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import vedro

from .._helpers import (
    create_mock_pipeline,
    create_mock_processor,
    create_mock_settings,
    create_mock_state_machine,
    create_processing_context,
)


class Scenario(vedro.Scenario):
    subject = "handle pipeline failure retry triggers pipeline failed when job retry exhausted"

    def given_processor_with_failed_pipeline_and_exhausted_job_retries(self):
        self.processor = create_mock_processor(settings=create_mock_settings(job_retry_count=1))

        self.pipeline = create_mock_pipeline(pipeline_id=100, sha="abc123", status="failed")

        # Job "unit_tests" already retried once, limit is 1 -> exhausted
        failed_job = MagicMock()
        failed_job.id = 10
        failed_job.name = "unit_tests"
        failed_job.status = "failed"
        self.processor.gitlab_client.get_pipeline_jobs = AsyncMock(return_value=[failed_job])

        self.mock_sm = create_mock_state_machine()
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.mock_sm)

        # unit_tests already retried once = at limit
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

    def and_pipeline_failed_is_triggered_on_state_machine(self):
        self.mock_sm.trigger_pipeline_failed.assert_awaited_once()
        call_kwargs = self.mock_sm.trigger_pipeline_failed.call_args.kwargs
        assert "unit_tests" in call_kwargs["failed_jobs"]

    def and_retry_pipeline_job_is_not_called(self):
        self.processor.gitlab_client.retry_pipeline_job.assert_not_called()
