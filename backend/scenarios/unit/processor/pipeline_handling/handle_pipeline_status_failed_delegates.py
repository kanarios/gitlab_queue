"""Test _handle_pipeline_status delegates to _handle_pipeline_failure when status is failed.

Line 993: when pipeline.status == "failed", call _handle_pipeline_failure and return its result.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import vedro

from gitlab_queue.core.processor import ProcessingResult

from .._helpers import (
    create_mock_pipeline,
    create_mock_processor,
    create_mock_state_machine,
    create_processing_context,
    create_test_queue_item,
)


class Scenario(vedro.Scenario):
    subject = "handle_pipeline_status delegates to handle_pipeline_failure for failed status"

    def given_processor_with_failed_pipeline(self):
        self.processor = create_mock_processor()

        self.queue_item = create_test_queue_item(mr_iid=42, state="testing")
        self.processor.queue_manager.get_queue_item.return_value = self.queue_item

        self.mock_sm = create_mock_state_machine()
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.mock_sm)

        self.pipeline = create_mock_pipeline(pipeline_id=100, sha="abc123", status="failed")

    async def when_handle_pipeline_status_is_called(self):
        with patch.object(
            self.processor._pipeline_handler,
            "handle_pipeline_failure",
            new_callable=AsyncMock,
            return_value=ProcessingResult.PIPELINE_FAILED,
        ) as self.mock_handle_failure:
            self.result = await self.processor._pipeline_handler.handle_pipeline_status(
                ctx=self.ctx,
                sm=self.mock_sm,
                pipeline=self.pipeline,
                retried_jobs={},
            )

    def then_result_is_pipeline_failed(self):
        assert self.result == ProcessingResult.PIPELINE_FAILED

    def and_handle_pipeline_failure_was_called(self):
        self.mock_handle_failure.assert_awaited_once()
