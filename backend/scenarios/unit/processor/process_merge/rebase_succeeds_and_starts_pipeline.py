"""Test _handle_pipeline_failure_retry persists retried_jobs to DB after job retry.

When job retry succeeds, the processor should persist the updated retried_jobs
dict to the database via update_mr_state so they survive restarts and webhook
race conditions.
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
    subject = "handle pipeline failure retry persists retried_jobs to DB after successful retry"

    def given_processor_with_failed_pipeline_and_retry_available(self):
        self.processor = create_mock_processor(settings=create_mock_settings(job_retry_count=2))

        self.pipeline = create_mock_pipeline(pipeline_id=100, sha="abc123", status="failed")

        failed_job = MagicMock()
        failed_job.id = 10
        failed_job.name = "unit_tests"
        failed_job.status = "failed"
        self.processor.gitlab_client.get_pipeline_jobs = AsyncMock(return_value=[failed_job])
        self.processor.gitlab_client.retry_pipeline_job = AsyncMock()
        self.processor.notifier.build_pipeline_url = AsyncMock(return_value="https://gitlab.com/p/100")

        self.mock_sm = create_mock_state_machine()
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.mock_sm)

        # No previous retries
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

    def and_retried_jobs_updated_correctly(self):
        assert self.updated_retried == {"unit_tests": 1}

    def and_update_mr_state_called_with_retried_jobs(self):
        self.processor.queue_manager.update_mr_state.assert_awaited_once()
        call_kwargs = self.processor.queue_manager.update_mr_state.call_args.kwargs
        assert call_kwargs.get("retried_jobs") == {"unit_tests": 1}

    def and_retry_count_not_passed_explicitly(self):
        call_kwargs = self.processor.queue_manager.update_mr_state.call_args.kwargs
        # retry_count is now auto-derived in queue.py, not passed explicitly
        assert "retry_count" not in call_kwargs

    def and_notify_job_retry_called(self):
        self.mock_sm.notify_job_retry.assert_awaited_once()

    def and_trigger_pipeline_failed_not_called(self):
        self.mock_sm.trigger_pipeline_failed.assert_not_awaited()
