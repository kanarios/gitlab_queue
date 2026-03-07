"""Test that matrix jobs with the same name are deduplicated in notify_job_retry call.

When two matrix jobs share the same name, notify_job_retry should receive
["rspec"], NOT ["rspec", "rspec"].
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
    subject = "matrix job names deduplicated in notify_job_retry call"

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

    def then_notify_job_retry_receives_deduplicated_names(self):
        assert len(self.mock_sm.job_retry_calls) == 1
        retried_job_names = self.mock_sm.job_retry_calls[0]["retried_jobs"]
        assert retried_job_names == ["rspec"], f"Expected ['rspec'] but got {retried_job_names}"

    def and_rspec_appears_exactly_once_in_notification(self):
        retried_job_names = self.mock_sm.job_retry_calls[0]["retried_jobs"]
        assert retried_job_names.count("rspec") == 1

    def and_both_jobs_were_actually_retried_via_api(self):
        assert len(self.processor.gitlab_client.retry_job_calls) == 2
