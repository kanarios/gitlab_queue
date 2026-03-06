"""Test _check_and_handle_rebase_during_testing stops when rebase has conflict.

When target branch changes during testing and rebase raises GitLabConflictError,
the processor should trigger conflict_during_testing and return CONFLICT result.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import vedro

from gitlab_queue.clients.gitlab import GitLabConflictError
from gitlab_queue.core.processor import ProcessingResult
from gitlab_queue.core.rebase_coordinator import check_and_handle_rebase_during_testing
from gitlab_queue.core.rebase_during_testing import RebaseDuringTestingContext, RebaseDuringTestingHandler

from .._helpers import (
    create_mock_pipeline,
    create_mock_processor,
    create_mock_state_machine,
    create_pipeline_wait_state,
    create_processing_context,
)


class Scenario(vedro.Scenario):
    subject = "rebase during testing conflict removes MR from queue"

    def given_processor_with_rebase_raising_conflict_during_testing(self):
        self.processor = create_mock_processor()

        self.pipeline = create_mock_pipeline(pipeline_id=100, sha="abc123", status="running")

        self.rebase_handler = AsyncMock(spec=RebaseDuringTestingHandler)
        self.rebase_handler.handle_rebase_if_needed = AsyncMock(
            side_effect=GitLabConflictError("Conflict during rebase")
        )

        self.processor.gitlab_client.get_mr_conflicts = AsyncMock(return_value=["src/file.py"])

        self.mock_sm = create_mock_state_machine()
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.mock_sm)

        self.rebase_ctx = RebaseDuringTestingContext(max_attempts=3)

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

    def then_result_is_conflict(self):
        assert self.result == ProcessingResult.CONFLICT

    def and_conflict_during_testing_was_triggered(self):
        self.mock_sm.trigger_conflict_during_testing.assert_awaited_once()

    def and_trigger_pipeline_failed_was_not_called(self):
        self.mock_sm.trigger_pipeline_failed.assert_not_awaited()
