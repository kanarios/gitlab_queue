"""Test that partial API error in job retry only reports the actually failed jobs.

When two jobs are retried and one succeeds while the other raises GitLabAPIError,
trigger_pipeline_failed should only report the job that actually failed,
not both jobs.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import vedro

from gitlab_queue.clients.gitlab import GitLabAPIError
from scenarios.fakes import FakeGitLabClient, create_job

if TYPE_CHECKING:
    from gitlab_queue.models.pipeline import Job

from .._helpers import (
    create_mock_pipeline,
    create_mock_processor,
    create_mock_state_machine,
    create_processing_context,
)


class _PartialErrorGitLabClient(FakeGitLabClient):
    """FakeGitLabClient that fails only for specific job IDs."""

    def __init__(self, *, fail_job_ids: set[int]) -> None:
        super().__init__()
        self.fail_job_ids = fail_job_ids

    async def retry_pipeline_job(self, job_id: int) -> Job:
        self.retry_job_calls.append(job_id)
        if job_id in self.fail_job_ids:
            raise GitLabAPIError("Retry failed for job")
        return create_job(id=job_id, status="pending")


class Scenario(vedro.Scenario):
    subject = "partial job retry API error reports only the failed jobs"

    def given_two_jobs_where_one_retry_fails(self):
        client = _PartialErrorGitLabClient(fail_job_ids={20})
        self.processor = create_mock_processor(gitlab_client=client)

        self.pipeline = create_mock_pipeline(pipeline_id=100, sha="abc123", status="failed")

        job_a = create_job(id=10, name="job_a", status="failed")
        job_b = create_job(id=20, name="job_b", status="failed")

        self.jobs_still_failed = [job_a, job_b]

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
        assert len(self.mock_sm.pipeline_failed_calls) == 1
        call = self.mock_sm.pipeline_failed_calls[0]
        assert call["failed_jobs"] == ["job_b"], f"Expected only ['job_b'] but got {call['failed_jobs']}"

    def and_job_a_is_not_reported_as_failed(self):
        call = self.mock_sm.pipeline_failed_calls[0]
        assert "job_a" not in call["failed_jobs"]
