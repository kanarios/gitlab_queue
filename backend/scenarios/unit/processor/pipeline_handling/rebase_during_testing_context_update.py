"""Test _check_and_handle_rebase_during_testing returns updated context with new pipeline.

When handle_rebase_if_needed succeeds and returns a new context with a
different pipeline ID, the handler should return a RebaseDuringTestingContext
instance indicating the rebase happened and a new pipeline was started.
"""

from __future__ import annotations

import vedro

from gitlab_queue.core.rebase_coordinator import check_and_handle_rebase_during_testing
from gitlab_queue.core.rebase_during_testing import RebaseDuringTestingContext
from scenarios.fakes import FakeRebaseDuringTestingHandler

from .._helpers import (
    create_mock_pipeline,
    create_mock_processor,
    create_mock_state_machine,
    create_pipeline_wait_state,
    create_processing_context,
)


class Scenario(vedro.Scenario):
    subject = "rebase during testing returns updated context with new pipeline"

    def given_processor_with_successful_rebase_during_testing(self):
        self.processor = create_mock_processor()

        self.mock_sm = create_mock_state_machine()
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.mock_sm)

        self.rebase_ctx = RebaseDuringTestingContext(rebase_count=0, max_attempts=3, current_pipeline_id=100)

        self.pipeline = create_mock_pipeline(pipeline_id=100, sha="abc123", status="running")

        self.new_pipeline = create_mock_pipeline(pipeline_id=200, sha="def456", status="running")

        self.new_ctx = RebaseDuringTestingContext(rebase_count=1, max_attempts=3, current_pipeline_id=200)

        self.rebase_handler = FakeRebaseDuringTestingHandler(
            result=(self.new_ctx, self.new_pipeline),
        )

    async def when_check_and_handle_rebase_during_testing_is_called(self):
        state = create_pipeline_wait_state(
            rebase_handler=self.rebase_handler,
            rebase_ctx=self.rebase_ctx,
        )
        self.result = await check_and_handle_rebase_during_testing(
            gitlab_client=self.processor.gitlab_client,
            ctx=self.ctx,
            state=state,
            pipeline=self.pipeline,
        )

    def then_result_is_rebase_during_testing_context(self):
        assert isinstance(self.result, RebaseDuringTestingContext)

    def and_context_has_updated_pipeline_id(self):
        assert self.result.current_pipeline_id == 200

    def and_context_has_incremented_rebase_count(self):
        assert self.result.rebase_count == 1

    def and_notify_rebase_during_testing_was_called(self):
        assert len(self.mock_sm.rebase_during_testing_calls) == 1
