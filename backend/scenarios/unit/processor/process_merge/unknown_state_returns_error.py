"""Test _execute_workflow returns ERROR for an unexpected state.

When the state machine has an unknown state that does not match any
of the expected workflow states (queued, rebasing, testing, merging),
the processor should return ProcessingResult.ERROR.
"""

from __future__ import annotations

import vedro

from gitlab_queue.core.processor import ProcessingResult

from .._helpers import (
    create_mock_processor,
    create_mock_state_machine,
    create_processing_context,
)


class Scenario(vedro.Scenario):
    subject = "execute workflow returns error for unknown state"

    def given_processor_with_mr_in_unknown_state(self):
        self.processor = create_mock_processor()

        self.mock_sm = create_mock_state_machine()
        self.mock_sm.current_state.id = "unknown_state"

        self.ctx = create_processing_context(mr_iid=42, state_machine=self.mock_sm)

    async def when_execute_workflow_is_called(self):
        self.result = await self.processor._execute_workflow(self.ctx)

    def then_result_is_error(self):
        assert self.result == ProcessingResult.ERROR
