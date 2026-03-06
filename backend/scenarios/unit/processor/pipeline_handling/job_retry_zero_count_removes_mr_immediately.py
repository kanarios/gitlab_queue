"""Test job_retry_count=0 removes MR immediately without retry.

When job_retry_count=0, no retries are allowed. MR should be removed
immediately on first failure without calling retry_pipeline_job.
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
    subject = "job_retry_count=0 removes MR immediately without retry"

    def given_processor_with_zero_retry_count(self):
        self.processor = create_mock_processor(settings=create_mock_settings(job_retry_count=0))

        self.pipeline = create_mock_pipeline(pipeline_id=100, sha="abc123", status="failed")

        failed_job = MagicMock()
        failed_job.id = 10
        failed_job.name = "unit_tests"
        failed_job.status = "failed"
        self.processor.gitlab_client.get_pipeline_jobs = AsyncMock(return_value=[failed_job])
        self.processor.gitlab_client.retry_pipeline_job = AsyncMock()

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

    def and_trigger_pipeline_failed_was_called(self):
        self.mock_sm.trigger_pipeline_failed.assert_awaited_once()

    def and_retry_pipeline_job_was_not_called(self):
        self.processor.gitlab_client.retry_pipeline_job.assert_not_awaited()
