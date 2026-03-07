"""Test sequence: double retry protection followed by real retry.

First poll:  pipeline=failed, jobs=running  → double retry (new_start_time=None)
Second poll: pipeline=failed, jobs=failed   → real retry   (new_start_time set)
"""

from __future__ import annotations

import vedro

from scenarios.fakes import create_job

from .._helpers import (
    create_mock_pipeline,
    create_mock_processor,
    create_mock_settings,
    create_mock_state_machine,
    create_processing_context,
)


class Scenario(vedro.Scenario):
    subject = "double retry protection then real retry increments counter correctly"

    def given_processor_and_pipeline(self):
        self.processor = create_mock_processor(settings=create_mock_settings(job_retry_count=1))
        self.pipeline = create_mock_pipeline(pipeline_id=100, sha="abc123", status="failed")

        self.running_job = create_job(id=10, name="unit_tests", status="running")
        self.failed_job = create_job(id=10, name="unit_tests", status="failed")

        self.mock_sm = create_mock_state_machine()
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.mock_sm)

    async def when_first_poll_sees_running_jobs(self):
        self.processor.gitlab_client.pipeline_jobs_response = [self.running_job]
        (
            self.first_should_continue,
            self.first_new_start_time,
            self.first_retried_jobs,
        ) = await self.processor._pipeline_handler.handle_pipeline_failure_retry(
            ctx=self.ctx,
            pipeline=self.pipeline,
            retried_jobs={},
        )
        self.retry_calls_after_first_poll = list(self.processor.gitlab_client.retry_job_calls)

    async def and_second_poll_sees_failed_jobs(self):
        self.processor.gitlab_client.pipeline_jobs_response = [self.failed_job]
        # Pass a copy so self.first_retried_jobs is not mutated by the second poll
        (
            self.second_should_continue,
            self.second_new_start_time,
            self.second_retried_jobs,
        ) = await self.processor._pipeline_handler.handle_pipeline_failure_retry(
            ctx=self.ctx,
            pipeline=self.pipeline,
            retried_jobs=dict(self.first_retried_jobs),
        )

    def then_first_poll_continues_without_resetting_timer(self):
        assert self.first_should_continue is True
        assert self.first_new_start_time is None

    def and_first_poll_does_not_change_retried_jobs(self):
        assert self.first_retried_jobs == {}

    def and_second_poll_triggers_real_retry(self):
        assert self.second_should_continue is True
        assert self.second_new_start_time is not None

    def and_second_poll_increments_retried_jobs(self):
        assert self.second_retried_jobs.get("unit_tests") == 1

    def and_first_poll_did_not_call_retry_api(self):
        assert self.retry_calls_after_first_poll == []

    def and_second_poll_called_retry_api_for_failed_job(self):
        assert self.failed_job.id in self.processor.gitlab_client.retry_job_calls
