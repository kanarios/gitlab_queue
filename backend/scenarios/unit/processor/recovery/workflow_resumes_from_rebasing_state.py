"""Test _execute_workflow resumes from rebasing state.

When the processor finds an MR with current_state "rebasing", it should
call _wait_for_rebase to complete the interrupted rebase, then continue
through the pipeline and merge steps.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import vedro

from gitlab_queue.core.processor import ProcessingResult

from .._helpers import (
    create_mock_processor,
    create_mock_state_machine,
    create_processing_context,
)


class Scenario(vedro.Scenario):
    subject = "execute workflow resumes from rebasing state"

    def given_processor_with_mr_in_rebasing_state(self):
        """
        Prepare a mock processor and a processing context whose state machine is in the "rebasing" state.

        Sets:
            self.processor: mock processor instance.
            self.mock_sm: mock state machine with current_state.id == "rebasing".
            self.ctx: processing context for MR IID 42 using the mock state machine.
        """
        self.processor = create_mock_processor()

        self.mock_sm = create_mock_state_machine()
        self.mock_sm.current_state.id = "rebasing"

        self.ctx = create_processing_context(mr_iid=42, state_machine=self.mock_sm)

    async def when_execute_workflow_is_called(self):
        """
        Execute the processor workflow with key steps stubbed to succeed and store the outcome in self.result.

        Patches the processor's _wait_for_rebase, _wait_for_pipeline, and _process_merge coroutines to return ProcessingResult.SUCCESS, then awaits _execute_workflow using self.ctx and assigns the returned ProcessingResult to self.result.
        """
        with (
            patch.object(
                self.processor,
                "_wait_for_rebase",
                new_callable=AsyncMock,
                return_value=ProcessingResult.SUCCESS,
            ) as self.mock_wait_for_rebase,
            patch.object(
                self.processor,
                "_wait_for_pipeline",
                new_callable=AsyncMock,
                return_value=ProcessingResult.SUCCESS,
            ),
            patch.object(
                self.processor,
                "_process_merge",
                new_callable=AsyncMock,
                return_value=ProcessingResult.SUCCESS,
            ),
        ):
            self.result = await self.processor._execute_workflow(self.ctx)

    def then_result_is_success(self):
        """
        Asserts that the scenario result indicates successful processing.

        Raises:
            AssertionError: If self.result is not ProcessingResult.SUCCESS.
        """
        assert self.result == ProcessingResult.SUCCESS

    def and_wait_for_rebase_was_called(self):
        """
        Asserts that the processor's `_wait_for_rebase` coroutine was awaited exactly once with the scenario's processing context.
        """
        self.mock_wait_for_rebase.assert_awaited_once_with(self.ctx)
