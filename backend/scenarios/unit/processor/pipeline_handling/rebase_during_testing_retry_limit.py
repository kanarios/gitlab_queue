"""Test _check_and_handle_rebase_during_testing returns PIPELINE_FAILED on retry limit.

When handle_rebase_if_needed raises RebaseRetryLimitExceeded, the handler
should trigger_pipeline_failed on the state machine and return
ProcessingResult.PIPELINE_FAILED.
"""

from __future__ import annotations

import vedro

from gitlab_queue.core.processor import ProcessingResult
from gitlab_queue.core.rebase_coordinator import check_and_handle_rebase_during_testing
from gitlab_queue.core.rebase_during_testing import (
    RebaseDuringTestingContext,
    RebaseRetryLimitExceeded,
)
from scenarios.fakes import FakeRebaseDuringTestingHandler

from .._helpers import (
    create_mock_pipeline,
    create_mock_processor,
    create_mock_state_machine,
    create_pipeline_wait_state,
    create_processing_context,
)


class Scenario(vedro.Scenario):
    subject = "rebase during testing returns pipeline failed on retry limit exceeded"

    def given_processor_with_rebase_retry_limit_exceeded(self):
        self.processor = create_mock_processor()

        self.mock_sm = create_mock_state_machine()
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.mock_sm)

        self.rebase_ctx = RebaseDuringTestingContext(rebase_count=3, max_attempts=3)

        self.pipeline = create_mock_pipeline(pipeline_id=100, sha="abc123", status="running")

        self.rebase_handler = FakeRebaseDuringTestingHandler(
            error=RebaseRetryLimitExceeded("MR !42: 3/3 rebase attempts exhausted"),
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

    def then_result_is_pipeline_failed(self):
        assert self.result == ProcessingResult.PIPELINE_FAILED

    def and_trigger_pipeline_failed_was_called(self):
        assert len(self.mock_sm.pipeline_failed_calls) == 1
