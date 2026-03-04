"""Test race condition: pipeline=failed but jobs already transitioning to running.

After job retry, GitLab transitions jobs to "running" before transitioning the pipeline.
The next poll sees pipeline.status="failed" + jobs.status="running".
Expected: continue polling (should_continue=True), NOT remove MR.
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
    subject = "pipeline failed but jobs are running: continue polling (race condition protection)"

    def given_processor_with_jobs_transitioning_to_running(self):
        self.processor = create_mock_processor(settings=create_mock_settings(job_retry_count=1))

        self.pipeline = create_mock_pipeline(pipeline_id=100, sha="abc123", status="failed")

        running_job = MagicMock()
        running_job.id = 10
        running_job.name = "unit_tests"
        running_job.status = "running"  # Job already transitioning after retry

        self.processor.gitlab_client.get_pipeline_jobs = AsyncMock(return_value=[running_job])
        self.processor.gitlab_client.retry_pipeline_job = AsyncMock()

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
        assert self.new_start_time is None

    def and_trigger_pipeline_failed_was_not_called(self):
        self.mock_sm.trigger_pipeline_failed.assert_not_awaited()

    def and_retry_pipeline_job_was_not_called(self):
        self.processor.gitlab_client.retry_pipeline_job.assert_not_called()
