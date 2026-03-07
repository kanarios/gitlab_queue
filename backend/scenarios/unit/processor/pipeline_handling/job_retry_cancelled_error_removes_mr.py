"""Test that asyncio.CancelledError during job retry causes MR removal.

asyncio.CancelledError inherits from BaseException (not Exception) in Python 3.8+.
isinstance(r, Exception) misses it → retry appears successful when it wasn't.
"""

from __future__ import annotations

import asyncio

import vedro

from scenarios.fakes import create_job

from .._helpers import (
    create_mock_pipeline,
    create_mock_processor,
    create_mock_state_machine,
    create_processing_context,
)


class Scenario(vedro.Scenario):
    subject = "CancelledError during job retry API call removes MR from queue"

    def given_processor_where_retry_raises_cancelled_error(self):
        self.processor = create_mock_processor()
        self.pipeline = create_mock_pipeline(pipeline_id=100, sha="abc123", status="failed")

        self.job_a = create_job(id=10, name="unit_tests", status="failed")

        self.processor.gitlab_client.retry_job_error = asyncio.CancelledError("Task cancelled")
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
            jobs_to_retry=[self.job_a],
            retried_jobs=self.retried_jobs,
            max_job_retries=1,
        )

    def then_should_continue_is_false(self):
        assert self.should_continue is False, "CancelledError must be treated as failure, not success"

    def and_new_start_time_is_none(self):
        assert self.new_start_time is None

    def and_trigger_pipeline_failed_was_called(self):
        assert len(self.mock_sm.pipeline_failed_calls) == 1

    def and_failed_job_is_reported(self):
        call = self.mock_sm.pipeline_failed_calls[0]
        assert "unit_tests" in call["failed_jobs"]
