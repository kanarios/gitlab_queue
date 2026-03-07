"""Test job retry API error removes MR from queue.

When retry_pipeline_job raises GitLabAPIError, the processor should
trigger pipeline_failed and return should_continue=False.
"""

from __future__ import annotations

import vedro

from gitlab_queue.clients.gitlab import GitLabAPIError
from scenarios.fakes import create_job

from .._helpers import (
    create_mock_pipeline,
    create_mock_processor,
    create_mock_settings,
    create_mock_state_machine,
    create_processing_context,
)


class Scenario(vedro.Scenario):
    subject = "job retry API error causes MR removal"

    def given_processor_with_retry_pipeline_job_failing(self):
        self.processor = create_mock_processor(settings=create_mock_settings(job_retry_count=1))

        self.pipeline = create_mock_pipeline(pipeline_id=100, sha="abc123", status="failed")

        failed_job = create_job(id=10, name="unit_tests", status="failed")
        self.processor.gitlab_client.pipeline_jobs_response = [failed_job]
        self.processor.gitlab_client.retry_job_error = GitLabAPIError("Retry failed")

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

    def then_should_continue_is_false(self):
        assert self.should_continue is False

    def and_new_start_time_is_none(self):
        assert self.new_start_time is None

    def and_trigger_pipeline_failed_was_called(self):
        assert len(self.mock_sm.pipeline_failed_calls) == 1
        call = self.mock_sm.pipeline_failed_calls[0]
        assert "unit_tests" in call["failed_jobs"]
