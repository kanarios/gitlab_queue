"""Test _handle_pipeline_status triggers pipeline_failed for non-actionable statuses.

Lines 997-1008: when pipeline has "skipped", "manual", or similar non-actionable status,
trigger_pipeline_failed and return PIPELINE_FAILED.
"""

from __future__ import annotations

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
    subject = "handle_pipeline_status returns PIPELINE_FAILED for non-actionable skipped status"

    def given_processor_with_skipped_pipeline(self):
        self.processor = create_mock_processor()

        self.queue_item = create_test_queue_item(mr_iid=42, state="testing")
        self.processor.queue_manager.get_queue_item.return_value = self.queue_item

        self.mock_sm = create_mock_state_machine()
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.mock_sm)

        self.pipeline = create_mock_pipeline(pipeline_id=100, sha="abc123", status="skipped")

    async def when_handle_pipeline_status_is_called(self):
        self.result = await self.processor._pipeline_handler.handle_pipeline_status(
            ctx=self.ctx,
            sm=self.mock_sm,
            pipeline=self.pipeline,
            retried_jobs={},
        )

    def then_result_is_pipeline_failed(self):
        assert self.result == ProcessingResult.PIPELINE_FAILED

    def and_trigger_pipeline_failed_was_called(self):
        self.mock_sm.trigger_pipeline_failed.assert_awaited_once()

    def and_error_message_mentions_skipped_status(self):
        call_kwargs = self.mock_sm.trigger_pipeline_failed.call_args.kwargs
        assert "skipped" in call_kwargs.get("error_message", "")
