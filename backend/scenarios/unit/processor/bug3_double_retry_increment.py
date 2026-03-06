"""Test: _handle_pipeline_failure syncs retried_jobs with DB to prevent double increment.

When the webhook handler already incremented retried_jobs in DB but the local
state is empty, _handle_pipeline_failure should sync the DB value so that
_handle_pipeline_failure_retry receives the correct, higher counts.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import vedro

from gitlab_queue.core.types import RetrySignal

from ._helpers import (
    create_mock_pipeline,
    create_mock_processor,
    create_mock_settings,
    create_processing_context,
    create_test_queue_item,
)


class Scenario(vedro.Scenario):
    subject = "processor uses DB retried_jobs when they are higher than local values"

    def given_processor_with_db_retried_jobs_ahead(self):
        # DB has retried_jobs={"flaky_test": 1} — webhook handler wrote it there
        self.queue_item = create_test_queue_item(mr_iid=42, state="testing", retried_jobs={"flaky_test": 1})
        settings = create_mock_settings(job_retry_count=3)
        self.processor = create_mock_processor(settings=settings)
        self.processor.queue_manager.get_queue_item = AsyncMock(return_value=self.queue_item)

        new_start = datetime.now(UTC)
        # After sync, _handle_pipeline_failure_retry receives {"flaky_test": 1} and returns retry signal
        self.processor._pipeline_handler.handle_pipeline_failure_retry = AsyncMock(
            return_value=(True, new_start, {"flaky_test": 1}),
        )

        self.ctx = create_processing_context(mr_iid=42)
        self.pipeline = create_mock_pipeline(status="failed")

    async def when_handle_pipeline_failure_is_called(self):
        # Local retried_jobs={} — DB has {"flaky_test": 1}, should be synced
        self.result = await self.processor._pipeline_handler.handle_pipeline_failure(
            self.ctx,
            self.pipeline,
            retried_jobs={},
        )

    def then_result_should_be_retry_signal(self):
        assert isinstance(self.result, RetrySignal), f"Expected RetrySignal, got {type(self.result)}"

    def and_retried_jobs_reflect_db_value(self):
        assert self.result.retried_jobs.get("flaky_test", 0) >= 1, (
            f"Expected flaky_test >= 1 in retried_jobs, got {self.result.retried_jobs}"
        )

    def and_retry_handler_was_called_with_synced_jobs(self):
        # Called as positional args: (ctx, pipeline, retried_jobs)
        call_args = self.processor._pipeline_handler.handle_pipeline_failure_retry.call_args
        retried = (
            call_args.args[2]
            if call_args.args and len(call_args.args) > 2
            else call_args.kwargs.get("retried_jobs", {})
        )
        assert retried.get("flaky_test", 0) >= 1, f"Expected flaky_test >= 1 passed to retry handler, got {retried}"
