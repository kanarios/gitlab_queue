"""Test that matrix jobs with the same name are not double-counted in retried_jobs.

When two parallel job instances share the same name (e.g. matrix jobs),
retrying both should increment the counter by 1 (per unique name), not 2.
"""

from __future__ import annotations

import vedro

from scenarios.fakes import create_job

from .._helpers import (
    create_mock_pipeline,
    create_mock_processor,
    create_mock_state_machine,
    create_processing_context,
)


class Scenario(vedro.Scenario):
    subject = "matrix jobs with same name are not double-counted in retried_jobs"

    def given_two_matrix_jobs_with_same_name(self):
        self.processor = create_mock_processor()

        self.pipeline = create_mock_pipeline(pipeline_id=100, sha="abc123", status="failed")

        job_a = create_job(id=10, name="rspec", status="failed")
        job_b = create_job(id=11, name="rspec", status="failed")

        self.jobs_still_failed = [job_a, job_b]
        self.retried_jobs: dict[str, int] = {}

        self.mock_sm = create_mock_state_machine()
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.mock_sm)

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
            max_job_retries=2,
        )

    def then_should_continue_is_true(self):
        assert self.should_continue is True

    def and_rspec_counter_is_incremented_once_not_twice(self):
        assert self.updated_retried.get("rspec") == 1, (
            f"Expected retried_jobs['rspec'] == 1 but got {self.updated_retried.get('rspec')}"
        )

    def and_both_jobs_were_actually_retried(self):
        assert len(self.processor.gitlab_client.retry_job_calls) == 2
