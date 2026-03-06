"""Test that retried_jobs loaded from DB prevent infinite retries after processor restart.

When the processor restarts and loads retried_jobs from DB, jobs that already
exhausted their retry budget should be removed immediately without additional retries.
This documents the restart-safety behavior.
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
    subject = "retried_jobs loaded from DB exhausts retry budget after restart"

    def given_processor_with_retried_jobs_already_at_max(self):
        settings = create_mock_settings(job_retry_count=1)
        self.processor = create_mock_processor(settings=settings)

        flaky_job = MagicMock()
        flaky_job.id = 10
        flaky_job.name = "flaky"
        flaky_job.status = "failed"

        self.processor.gitlab_client.get_pipeline_jobs = AsyncMock(return_value=[flaky_job])
        self.processor.gitlab_client.retry_pipeline_job = AsyncMock()

        self.pipeline = create_mock_pipeline(pipeline_id=100, sha="abc123", status="failed")

        self.mock_sm = create_mock_state_machine()
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.mock_sm)

        # retried_jobs loaded from DB: flaky already retried once, max is 1
        self.retried_jobs_from_db: dict[str, int] = {"flaky": 1}

    async def when_handle_pipeline_failure_retry_is_called(self):
        (
            self.should_continue,
            self.new_start_time,
            self.updated_retried,
        ) = await self.processor._pipeline_handler.handle_pipeline_failure_retry(
            ctx=self.ctx,
            pipeline=self.pipeline,
            retried_jobs=self.retried_jobs_from_db,
        )

    def then_should_continue_is_false(self):
        assert self.should_continue is False

    def and_mr_is_removed_without_additional_retry(self):
        self.processor.gitlab_client.retry_pipeline_job.assert_not_awaited()

    def and_trigger_pipeline_failed_was_called(self):
        self.mock_sm.trigger_pipeline_failed.assert_awaited_once()
        call_kwargs = self.mock_sm.trigger_pipeline_failed.call_args.kwargs
        assert "flaky" in call_kwargs["failed_jobs"]
