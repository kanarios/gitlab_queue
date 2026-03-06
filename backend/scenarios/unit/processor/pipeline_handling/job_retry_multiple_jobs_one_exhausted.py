"""Test job retry: when one of multiple jobs is exhausted, MR is removed.

When two jobs fail but one has exceeded its retry limit, the MR should be
removed immediately. retry_pipeline_job should NOT be called for any job.
"""

from __future__ import annotations

from unittest.mock import ANY, AsyncMock, MagicMock

import vedro

from .._helpers import (
    create_mock_pipeline,
    create_mock_processor,
    create_mock_settings,
    create_mock_state_machine,
    create_processing_context,
)


class Scenario(vedro.Scenario):
    subject = "job retry: one exhausted job among multiple fails causes MR removal"

    def given_processor_with_two_failed_jobs_one_exhausted(self):
        self.processor = create_mock_processor(settings=create_mock_settings(job_retry_count=1))

        self.pipeline = create_mock_pipeline(pipeline_id=100, sha="abc123", status="failed")

        flaky_job = MagicMock()
        flaky_job.id = 10
        flaky_job.name = "flaky_test"
        flaky_job.status = "failed"

        exhausted_job = MagicMock()
        exhausted_job.id = 11
        exhausted_job.name = "unit_tests"
        exhausted_job.status = "failed"

        self.processor.gitlab_client.get_pipeline_jobs = AsyncMock(return_value=[flaky_job, exhausted_job])
        self.processor.gitlab_client.retry_pipeline_job = AsyncMock()

        self.mock_sm = create_mock_state_machine()
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.mock_sm)

        # unit_tests already at limit, flaky_test not yet retried
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

    def and_updated_retried_is_unchanged(self):
        assert self.updated_retried == self.retried_jobs

    def and_trigger_pipeline_failed_was_called(self):
        self.mock_sm.trigger_pipeline_failed.assert_awaited_once_with(
            failed_jobs=["unit_tests"],
            retried_jobs={"unit_tests": 1},
            error_message=ANY,
        )

    def and_retry_pipeline_job_was_not_called(self):
        self.processor.gitlab_client.retry_pipeline_job.assert_not_called()
