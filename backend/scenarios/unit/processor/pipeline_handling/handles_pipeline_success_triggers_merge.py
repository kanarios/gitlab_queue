"""Test _handle_pipeline_status triggers pipeline_success on success status.

When a pipeline has status "success" and the SHA matches the expected SHA
in the queue item, _handle_pipeline_status should trigger trigger_pipeline_success
on the state machine and return ProcessingResult.SUCCESS.
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
    subject = "handle pipeline status triggers pipeline success for successful pipeline"

    def given_processor_with_successful_pipeline_matching_sha(self):
        self.processor = create_mock_processor()

        self.queue_item = create_test_queue_item(mr_iid=42, state="testing", expected_sha="abc123")
        self.processor.queue_manager.get_queue_item.return_value = self.queue_item

        self.mock_sm = create_mock_state_machine()
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.mock_sm)

        self.pipeline = create_mock_pipeline(pipeline_id=100, sha="abc123", status="success")

    async def when_handle_pipeline_status_is_called(self):
        self.result = await self.processor._handle_pipeline_status(
            ctx=self.ctx,
            sm=self.mock_sm,
            pipeline=self.pipeline,
            retry_count=0,
            max_retries=1,
        )

    def then_result_is_success(self):
        assert self.result == ProcessingResult.SUCCESS

    def and_pipeline_success_is_triggered_on_state_machine(self):
        self.mock_sm.trigger_pipeline_success.assert_called_once()

    def and_pipeline_failed_is_not_triggered(self):
        self.mock_sm.trigger_pipeline_failed.assert_not_called()
