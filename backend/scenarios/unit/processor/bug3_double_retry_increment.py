"""Test: _handle_pipeline_failure syncs retry_count with DB to prevent double increment."""

from __future__ import annotations

from unittest.mock import AsyncMock

import vedro

from gitlab_queue.core.processor import RetrySignal

from ._helpers import (
    create_mock_pipeline,
    create_mock_processor,
    create_mock_settings,
    create_processing_context,
    create_test_queue_item,
)


class Scenario(vedro.Scenario):
    subject = "processor uses DB retry_count when it is higher than local value"

    def given_processor_with_db_retry_count_ahead(self):
        # Webhook handler already incremented retry_count to 1 in DB
        self.queue_item = create_test_queue_item(mr_iid=42, state="testing", retry_count=1)
        settings = create_mock_settings(pipeline_retry_count=3)
        self.processor = create_mock_processor(settings=settings)
        self.processor.queue_manager.get_queue_item = AsyncMock(return_value=self.queue_item)
        self.processor.gitlab_client.get_pipeline_jobs = AsyncMock(return_value=[])

        # Mock _handle_pipeline_failure_retry to return True (should retry)
        self.processor._handle_pipeline_failure_retry = AsyncMock(
            return_value=(True, self.queue_item.queued_at),
        )

        self.ctx = create_processing_context(mr_iid=42)
        self.pipeline = create_mock_pipeline(status="failed")

    async def when_handle_pipeline_failure_is_called(self):
        # Local retry_count=0, but DB has retry_count=1
        self.result = await self.processor._handle_pipeline_failure(
            self.ctx,
            self.pipeline,
            retry_count=0,
            max_retries=3,
        )

    def then_result_should_be_retry_signal(self):
        assert isinstance(self.result, RetrySignal), f"Expected RetrySignal, got {type(self.result)}"

    def and_retry_count_should_reflect_db_value(self):
        # DB has 1, so after retry it should be 2 (1 + 1), not 1 (0 + 1)
        assert self.result.retry_count >= 2, f"Expected retry_count >= 2, got {self.result.retry_count}"
