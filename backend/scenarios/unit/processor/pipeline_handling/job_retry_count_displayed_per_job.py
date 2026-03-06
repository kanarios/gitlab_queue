"""Test trigger_pipeline_failed receives retried_jobs dict with per-job counts.

When MR is removed due to exhausted retries, trigger_pipeline_failed should
receive retried_jobs as a dict showing per-job retry counts.
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
    subject = "trigger_pipeline_failed receives per-job retry counts"

    def given_processor_with_multiple_jobs_at_retry_limit(self):
        self.processor = create_mock_processor(settings=create_mock_settings(job_retry_count=2))

        self.pipeline = create_mock_pipeline(pipeline_id=100, sha="abc123", status="failed")

        # test job exhausted (2 retries done, limit=2)
        test_job = MagicMock()
        test_job.id = 10
        test_job.name = "test"
        test_job.status = "failed"

        self.processor.gitlab_client.get_pipeline_jobs = AsyncMock(return_value=[test_job])
        self.processor.gitlab_client.retry_pipeline_job = AsyncMock()

        self.mock_sm = create_mock_state_machine()
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.mock_sm)

        # test: 2 retries (at job_retry_count limit), lint: 1 retry (below limit)
        self.retried_jobs = {"test": 2, "lint": 1}

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

    def then_trigger_pipeline_failed_receives_retried_jobs_dict(self):
        self.mock_sm.trigger_pipeline_failed.assert_awaited_once()
        call_kwargs = self.mock_sm.trigger_pipeline_failed.call_args.kwargs
        assert "retried_jobs" in call_kwargs
        assert isinstance(call_kwargs["retried_jobs"], dict)

    def and_retried_jobs_contains_per_job_counts(self):
        call_kwargs = self.mock_sm.trigger_pipeline_failed.call_args.kwargs
        assert call_kwargs["retried_jobs"].get("test") == 2
        assert call_kwargs["retried_jobs"].get("lint") == 1
