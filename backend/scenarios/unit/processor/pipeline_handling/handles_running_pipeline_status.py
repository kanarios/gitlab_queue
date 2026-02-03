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
        self.processor = create_mock_processor()

        self.mock_sm = create_mock_state_machine()
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.mock_sm)

        self.pipeline = create_mock_pipeline(pipeline_id=100, sha="abc123", status="running")

    async def when_handle_pipeline_status_is_called(self):
        self.result = await self.processor._handle_pipeline_status(
            ctx=self.ctx,
            sm=self.mock_sm,
            pipeline=self.pipeline,
            retry_count=0,
            max_retries=1,
        )

    def then_result_is_none_indicating_continue_polling(self):
        assert self.result is None

    def and_no_state_machine_transitions_are_triggered(self):
        self.mock_sm.trigger_pipeline_success.assert_not_called()
        self.mock_sm.trigger_pipeline_failed.assert_not_called()
