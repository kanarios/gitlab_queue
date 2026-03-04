"""Test job_retry_count=2 allows second retry.

When job_retry_count=2 and job has been retried once (retried_jobs={"flaky": 1}),
the processor should allow a second retry (not remove MR).
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
    subject = "job_retry_count=2 allows second retry attempt"

    def given_processor_with_job_retried_once_and_limit_two(self):
        self.processor = create_mock_processor(settings=create_mock_settings(job_retry_count=2))

        self.pipeline = create_mock_pipeline(pipeline_id=100, sha="abc123", status="failed")

        failed_job = MagicMock()
        failed_job.id = 10
        failed_job.name = "flaky"
        failed_job.status = "failed"
        self.processor.gitlab_client.get_pipeline_jobs = AsyncMock(return_value=[failed_job])
        self.processor.gitlab_client.retry_pipeline_job = AsyncMock()
        self.processor.notifier.build_pipeline_url = AsyncMock(return_value="https://gitlab.com/pipeline/100")

        self.mock_sm = create_mock_state_machine()
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.mock_sm)

        # flaky retried once, but limit is 2 → second retry allowed
        self.retried_jobs = {"flaky": 1}

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

    def and_trigger_pipeline_failed_is_not_called(self):
        self.mock_sm.trigger_pipeline_failed.assert_not_awaited()

    def and_retry_pipeline_job_was_called(self):
        self.processor.gitlab_client.retry_pipeline_job.assert_awaited_once_with(10)

    def and_retried_jobs_count_updated_to_two(self):
        assert self.updated_retried.get("flaky") == 2
