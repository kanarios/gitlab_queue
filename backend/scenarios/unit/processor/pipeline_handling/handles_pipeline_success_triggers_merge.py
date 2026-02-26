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
        """
        Prepare test fixtures: a mock processor, queue item, processing context with a mock state machine, and a mock pipeline whose SHA matches the queue item's expected SHA and whose status is "success".

        Sets:
        - self.processor: mock processor
        - self.queue_item: queue item with mr_iid=42, state="testing", expected_sha="abc123" (returned by processor.queue_manager.get_queue_item)
        - self.mock_sm: mock state machine
        - self.ctx: processing context with mr_iid=42 and the mock state machine
        - self.pipeline: mock pipeline with pipeline_id=100, sha="abc123", status="success"
        """
        self.processor = create_mock_processor()

        self.queue_item = create_test_queue_item(mr_iid=42, state="testing", expected_sha="abc123")
        self.processor.queue_manager.get_queue_item.return_value = self.queue_item

        self.mock_sm = create_mock_state_machine()
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.mock_sm)

        self.pipeline = create_mock_pipeline(pipeline_id=100, sha="abc123", status="success")

    async def when_handle_pipeline_status_is_called(self):
        """
        Invoke the processor's _handle_pipeline_status with the prepared context, state machine, and pipeline, and store the returned processing result on self.result.

        This awaits the asynchronous call using retry_count=0 and max_retries=1 and assigns its result to the instance attribute `self.result` for later assertions.
        """
        self.result = await self.processor._handle_pipeline_status(
            ctx=self.ctx,
            sm=self.mock_sm,
            pipeline=self.pipeline,
            retry_count=0,
            max_retries=1,
        )

    def then_result_is_success(self):
        """
        Asserts that the scenario's processing result equals ProcessingResult.SUCCESS.

        Raises:
            AssertionError: If the result is not ProcessingResult.SUCCESS.
        """
        assert self.result == ProcessingResult.SUCCESS

    def and_pipeline_success_is_triggered_on_state_machine(self):
        """
        Asserts that the state machine's pipeline-success trigger was awaited exactly once.

        This verifies the scenario invoked the state machine's `trigger_pipeline_success` coroutine one time.
        """
        self.mock_sm.trigger_pipeline_success.assert_awaited_once()

    def and_pipeline_failed_is_not_triggered(self):
        """
        Asserts that the state machine's trigger_pipeline_failed method was not awaited.

        Raises:
            AssertionError: If trigger_pipeline_failed was awaited one or more times.
        """
        self.mock_sm.trigger_pipeline_failed.assert_not_awaited()
