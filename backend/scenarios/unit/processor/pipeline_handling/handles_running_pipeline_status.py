"""Test _handle_pipeline_status returns None for a running pipeline.

When a pipeline has status "running", _handle_pipeline_status should
return None, signalling the polling loop to continue waiting without
taking any action.
"""

from __future__ import annotations

import vedro

from .._helpers import (
    create_mock_pipeline,
    create_mock_processor,
    create_mock_state_machine,
    create_processing_context,
)


class Scenario(vedro.Scenario):
    subject = "handle pipeline status returns None for running pipeline"

    def given_processor_with_running_pipeline(self):
        """
        Set up a mock processor, a mock state machine, a processing context, and a pipeline with status "running" for the test scenario.

        This initializes the following attributes on self:
        - processor: a mock processor instance
        - mock_sm: a mock state machine
        - ctx: a processing context with mr_iid=42 and the mock state machine attached
        - pipeline: a mock pipeline with pipeline_id=100, sha="abc123", and status="running"
        """
        self.processor = create_mock_processor()

        self.mock_sm = create_mock_state_machine()
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.mock_sm)

        self.pipeline = create_mock_pipeline(pipeline_id=100, sha="abc123", status="running")

    async def when_handle_pipeline_status_is_called(self):
        """
        Calls the processor's _handle_pipeline_status with the prepared context, state machine, and pipeline and stores the outcome in self.result.

        This invokes the handler with retry_count=0 and max_retries=1 to capture the handler's response for a pipeline in the "running" state.
        """
        self.result = await self.processor._pipeline_handler.handle_pipeline_status(
            ctx=self.ctx,
            sm=self.mock_sm,
            pipeline=self.pipeline,
            retried_jobs={},
        )

    def then_result_is_none_indicating_continue_polling(self):
        """
        Assert that the handler returned None to indicate polling should continue.

        Raises:
            AssertionError: If `self.result` is not `None`.
        """
        assert self.result is None

    def and_no_state_machine_transitions_are_triggered(self):
        self.mock_sm.trigger_pipeline_success.assert_not_awaited()
        self.mock_sm.trigger_pipeline_failed.assert_not_awaited()
