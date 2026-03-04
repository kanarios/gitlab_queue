"""Test that matrix jobs with the same name are deduplicated in notify_job_retry call.

When two matrix jobs share the same name, notify_job_retry should receive
["rspec"], NOT ["rspec", "rspec"].
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import vedro

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
        self.processor.gitlab_client.retry_pipeline_job = AsyncMock()
        self.processor.notifier.build_pipeline_url = AsyncMock(return_value="https://gitlab.com/pipeline/100")
        self.pipeline = create_mock_pipeline(pipeline_id=100, sha="abc123", status="failed")

        job_a = MagicMock()
        job_a.id = 10
        job_a.name = "rspec"
        job_a.status = "failed"

        job_b = MagicMock()
        job_b.id = 11
        job_b.name = "rspec"
        job_b.status = "failed"

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
        self.mock_sm.notify_job_retry.assert_awaited_once()
        call_kwargs = self.mock_sm.notify_job_retry.call_args.kwargs
        retried_job_names = call_kwargs["retried_jobs"]
        assert retried_job_names == ["rspec"], f"Expected ['rspec'] but got {retried_job_names}"

    def and_rspec_appears_exactly_once_in_notification(self):
        call_kwargs = self.mock_sm.notify_job_retry.call_args.kwargs
        assert call_kwargs["retried_jobs"].count("rspec") == 1

    def and_both_jobs_were_actually_retried_via_api(self):
        assert self.processor.gitlab_client.retry_pipeline_job.await_count == 2
