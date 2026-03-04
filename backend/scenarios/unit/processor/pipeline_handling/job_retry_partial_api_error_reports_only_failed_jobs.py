"""Test that partial API error in job retry only reports the actually failed jobs.

When two jobs are retried and one succeeds while the other raises GitLabAPIError,
trigger_pipeline_failed should only report the job that actually failed,
not both jobs.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import vedro

from gitlab_queue.clients.gitlab import GitLabAPIError

from .._helpers import (
    create_mock_pipeline,
    create_mock_processor,
    create_mock_state_machine,
    create_processing_context,
)


class Scenario(vedro.Scenario):
    subject = "partial job retry API error reports only the failed jobs"

    def given_two_jobs_where_one_retry_fails(self):
        self.processor = create_mock_processor()

        self.pipeline = create_mock_pipeline(pipeline_id=100, sha="abc123", status="failed")

        job_a = MagicMock()
        job_a.id = 10
        job_a.name = "job_a"
        job_a.status = "failed"

        job_b = MagicMock()
        job_b.id = 20
        job_b.name = "job_b"
        job_b.status = "failed"

        self.jobs_still_failed = [job_a, job_b]

        async def retry_side_effect(job_id: int) -> None:
            if job_id == 20:
                raise GitLabAPIError("Retry failed for job_b")

        self.processor.gitlab_client.retry_pipeline_job = AsyncMock(side_effect=retry_side_effect)

        self.mock_sm = create_mock_state_machine()
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.mock_sm)

        self.retried_jobs: dict[str, int] = {}

    async def when_dispatch_job_retries_is_called(self):
        (
            self.should_continue,
            self.new_start_time,
            self.updated_retried,
        ) = await self.processor._pipeline_handler.dispatch_job_retries(
            ctx=self.ctx,
            pipeline=self.pipeline,
            jobs_to_retry=self.jobs_still_failed,
            retried_jobs=self.retried_jobs,
            max_job_retries=1,
        )

    def then_should_continue_is_false(self):
        assert self.should_continue is False

    def and_trigger_pipeline_failed_reports_only_job_b(self):
        self.mock_sm.trigger_pipeline_failed.assert_awaited_once()
        call_kwargs = self.mock_sm.trigger_pipeline_failed.call_args.kwargs
        assert call_kwargs["failed_jobs"] == ["job_b"], f"Expected only ['job_b'] but got {call_kwargs['failed_jobs']}"

    def and_job_a_is_not_reported_as_failed(self):
        call_kwargs = self.mock_sm.trigger_pipeline_failed.call_args.kwargs
        assert "job_a" not in call_kwargs["failed_jobs"]
