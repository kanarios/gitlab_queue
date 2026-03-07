"""Test _handle_pipeline_failure_retry when jobs can be retried.

When a pipeline fails and failed jobs have not exhausted their retry count,
the processor should retry individual failed jobs and signal the caller to
continue polling.

Covers handle_pipeline_failure_retry: job-level retry path that calls
retry_pipeline_job and returns (True, new_start, updated_retried_jobs).
"""

from __future__ import annotations

from datetime import datetime

import vedro

from scenarios.fakes import create_job

from .._helpers import (
    create_mock_pipeline,
    create_mock_processor,
    create_mock_state_machine,
    create_processing_context,
)


class Scenario(vedro.Scenario):
    subject = "handle pipeline failure retry returns retry signal for job-level retry path"

    def given_processor_with_failed_pipeline_and_retry_available(self):
        self.processor = create_mock_processor()

        # Old pipeline (the one that failed)
        self.old_pipeline = create_mock_pipeline(pipeline_id=100, sha="sha_old", status="failed")

        # Pipeline has a single failed job that can be retried
        self.processor.gitlab_client.pipeline_jobs_response = [
            create_job(id=10, name="test_job", status="failed"),
        ]

        self.mock_sm = create_mock_state_machine()
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.mock_sm)

    async def when_handle_pipeline_failure_retry_is_called(self):
        (
            self.should_continue,
            self.new_start_time,
            self.updated_retried,
        ) = await self.processor._handle_pipeline_failure_retry(
            ctx=self.ctx,
            pipeline=self.old_pipeline,
            retried_jobs={},
        )

    def then_should_continue_is_true(self):
        assert self.should_continue is True

    def and_new_start_time_is_set(self):
        assert self.new_start_time is not None
        assert isinstance(self.new_start_time, datetime)

    def and_job_retry_is_notified_on_state_machine(self):
        assert len(self.mock_sm.job_retry_calls) == 1
        call_kwargs = self.mock_sm.job_retry_calls[0]
        assert call_kwargs["pipeline_id"] == 100
        assert "test_job" in call_kwargs["retried_jobs"]

    def and_pipeline_failed_is_not_triggered(self):
        assert self.mock_sm.pipeline_failed_calls == []

    def and_retried_jobs_tracks_the_job(self):
        assert "test_job" in self.updated_retried
        assert self.updated_retried["test_job"] == 1
