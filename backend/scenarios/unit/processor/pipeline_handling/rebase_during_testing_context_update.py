"""Test _check_and_handle_rebase_during_testing returns updated context with new pipeline.

When handle_rebase_if_needed succeeds and returns a new context with a
different pipeline ID, the handler should return a RebaseDuringTestingContext
instance indicating the rebase happened and a new pipeline was started.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import vedro

from gitlab_queue.core.rebase_during_testing import RebaseDuringTestingContext

from .._helpers import (
    create_mock_pipeline,
    create_mock_processor,
    create_mock_state_machine,
    create_processing_context,
)


class Scenario(vedro.Scenario):
    subject = "rebase during testing returns updated context with new pipeline"

    def given_processor_with_successful_rebase_during_testing(self):
        """
        Prepare test fixtures simulating a successful rebase during testing.

        Creates and attaches to self:
        - processor: mock processor instance.
        - mock_sm: mock state machine and ctx: processing context with mr_iid=42.
        - rebase_ctx: initial RebaseDuringTestingContext (rebase_count=0, max_attempts=3, current_pipeline_id=100).
        - pipeline: mock pipeline with pipeline_id=100.
        - new_pipeline: mock pipeline with pipeline_id=200.
        - new_ctx: RebaseDuringTestingContext after rebase (rebase_count=1, current_pipeline_id=200).
        - rebase_handler: MagicMock whose handle_rebase_if_needed coroutine returns (new_ctx, new_pipeline).
        """
        self.processor = create_mock_processor()

        self.mock_sm = create_mock_state_machine()
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.mock_sm)

        self.rebase_ctx = RebaseDuringTestingContext(rebase_count=0, max_attempts=3, current_pipeline_id=100)

        self.pipeline = create_mock_pipeline(pipeline_id=100, sha="abc123", status="running")

        self.new_pipeline = create_mock_pipeline(pipeline_id=200, sha="def456", status="running")

        self.new_ctx = RebaseDuringTestingContext(rebase_count=1, max_attempts=3, current_pipeline_id=200)

        self.rebase_handler = MagicMock()
        self.rebase_handler.handle_rebase_if_needed = AsyncMock(return_value=(self.new_ctx, self.new_pipeline))

    async def when_check_and_handle_rebase_during_testing_is_called(self):
        self.result = await self.processor._check_and_handle_rebase_during_testing(
            ctx=self.ctx,
            sm=self.mock_sm,
            rebase_handler=self.rebase_handler,
            rebase_ctx=self.rebase_ctx,
            pipeline=self.pipeline,
            retry_count=0,
        )

    def then_result_is_rebase_during_testing_context(self):
        assert isinstance(self.result, RebaseDuringTestingContext)

    def and_context_has_updated_pipeline_id(self):
        """
        Verifies that the scenario result's RebaseDuringTestingContext has current_pipeline_id equal to 200.
        """
        assert self.result.current_pipeline_id == 200

    def and_context_has_incremented_rebase_count(self):
        assert self.result.rebase_count == 1

    def and_notify_rebase_during_testing_was_called(self):
        self.mock_sm.notify_rebase_during_testing.assert_awaited_once()
