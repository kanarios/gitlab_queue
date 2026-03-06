"""Test _execute_workflow returns early when _process_rebase fails in queued state.

Line 331: return result when _process_rebase returns non-SUCCESS in the queued path.
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
    subject = "execute workflow returns early when rebase fails in queued state"

    def given_processor_with_queued_mr_and_failing_rebase(self):
        self.processor = create_mock_processor()
        self.mock_sm = create_mock_state_machine()
        self.mock_sm.current_state.id = "queued"
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.mock_sm)

    async def when_execute_workflow_is_called(self):
        with patch.object(
            self.processor,
            "_process_rebase",
            new_callable=AsyncMock,
            return_value=ProcessingResult.CONFLICT,
        ):
            self.result = await self.processor._execute_workflow(self.ctx)

    def then_result_is_conflict(self):
        assert self.result == ProcessingResult.CONFLICT

    def and_trigger_start_processing_was_called(self):
        self.mock_sm.trigger_start_processing.assert_awaited_once()
