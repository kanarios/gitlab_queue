"""Test _check_and_handle_rebase_during_testing returns PIPELINE_FAILED on retry limit.

When handle_rebase_if_needed raises RebaseRetryLimitExceeded, the handler
should trigger_pipeline_failed on the state machine and return
ProcessingResult.PIPELINE_FAILED.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import vedro

from gitlab_queue.core.processor import ProcessingResult
from gitlab_queue.core.rebase_during_testing import (
    RebaseDuringTestingContext,
    RebaseRetryLimitExceeded,
)

from .._helpers import (
    create_mock_pipeline,
    create_mock_processor,
    create_mock_state_machine,
    create_processing_context,
)


class Scenario(vedro.Scenario):
    subject = "rebase during testing returns pipeline failed on retry limit exceeded"

    def given_processor_with_rebase_retry_limit_exceeded(self):
        """
        Prepare a processor and related mocks configured to simulate hitting the rebase retry limit during testing.

        Sets up:
        - a mock processor,
        - a mock state machine and processing context with mr_iid=42,
        - a RebaseDuringTestingContext with rebase_count and max_attempts both set to 3,
        - a running mock pipeline (id 100, sha "abc123"),
        - a rebase_handler whose handle_rebase_if_needed coroutine raises RebaseRetryLimitExceeded("MR !42: 3/3 rebase attempts exhausted").
        """
        self.processor = create_mock_processor()

        self.mock_sm = create_mock_state_machine()
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.mock_sm)

        self.rebase_ctx = RebaseDuringTestingContext(rebase_count=3, max_attempts=3)

        self.pipeline = create_mock_pipeline(pipeline_id=100, sha="abc123", status="running")

        self.rebase_handler = MagicMock()
        self.rebase_handler.handle_rebase_if_needed = AsyncMock(
            side_effect=RebaseRetryLimitExceeded("MR !42: 3/3 rebase attempts exhausted")
        )

    async def when_check_and_handle_rebase_during_testing_is_called(self):
        self.result = await self.processor._check_and_handle_rebase_during_testing(
            ctx=self.ctx,
            sm=self.mock_sm,
            rebase_handler=self.rebase_handler,
            rebase_ctx=self.rebase_ctx,
            pipeline=self.pipeline,
            retry_count=0,
        )

    def then_result_is_pipeline_failed(self):
        """
        Assert that the scenario result is ProcessingResult.PIPELINE_FAILED.
        """
        assert self.result == ProcessingResult.PIPELINE_FAILED

    def and_trigger_pipeline_failed_was_called(self):
        self.mock_sm.trigger_pipeline_failed.assert_awaited_once()
