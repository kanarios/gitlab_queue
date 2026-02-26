"""Test _handle_pipeline_status returns None when SHA does not match.

When a pipeline reports status "success" but its SHA does not match the
expected_sha stored in the queue item, the handler should return None
to signal the polling loop to continue waiting for the correct pipeline.
"""

from __future__ import annotations

import vedro

from .._helpers import (
    create_mock_pipeline,
    create_mock_processor,
    create_mock_state_machine,
    create_processing_context,
    create_test_queue_item,
)


class Scenario(vedro.Scenario):
    subject = "handle pipeline status returns none on sha mismatch"

    def given_processor_with_success_pipeline_wrong_sha(self):
        # Pipeline reports success but SHA does not match the queue item's
        # expected_sha.
        self.processor = create_mock_processor()

        self.queue_item = create_test_queue_item(
            mr_iid=42,
            state="testing",
            expected_sha="different_sha",
        )
        self.processor.queue_manager.get_queue_item.return_value = self.queue_item

        self.pipeline = create_mock_pipeline(
            pipeline_id=100,
            sha="abc123",
            status="success",
        )

        self.mock_sm = create_mock_state_machine()
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.mock_sm)

    async def when_handle_pipeline_status_is_called(self):
        """
        Invoke the processor's _handle_pipeline_status with the prepared
        context, mock state machine, and pipeline, and store the handler's
        return value on self.result.

        The call uses retry_count=0 and max_retries=1 to simulate the initial
        handling attempt.
        """
        self.result = await self.processor._handle_pipeline_status(
            ctx=self.ctx,
            sm=self.mock_sm,
            pipeline=self.pipeline,
            retry_count=0,
            max_retries=1,
        )

    def then_result_is_none_indicating_continue_polling(self):
        """
        Asserts that the handler returned None to indicate the polling loop
        should continue.

        Verifies that no terminal pipeline action was triggered and polling
        should keep waiting for a matching SHA.
        """
        assert self.result is None

    def and_pipeline_success_is_not_triggered(self):
        """
        Asserts that the state machine's pipeline-success trigger was not
        awaited.

        This verifies that trigger_pipeline_success on the mocked state machine
        was not called during the test.
        """
        self.mock_sm.trigger_pipeline_success.assert_not_awaited()

    def and_pipeline_failed_is_not_triggered(self):
        """
        Asserts that the state machine's pipeline failure trigger was not
        invoked.

        This verifies that mock_sm.trigger_pipeline_failed was not awaited
        during the test.
        """
        self.mock_sm.trigger_pipeline_failed.assert_not_awaited()
