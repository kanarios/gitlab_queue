"""Test _execute_workflow returns early when _wait_for_rebase fails in rebasing state.

Line 340: return result when _wait_for_rebase returns non-SUCCESS in the rebasing path.
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
    subject = "execute workflow returns early when wait_for_rebase fails in rebasing state"

    def given_processor_with_rebasing_mr_and_timeout(self):
        self.processor = create_mock_processor()
        self.mock_sm = create_mock_state_machine()
        self.mock_sm.current_state.id = "rebasing"
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.mock_sm)

    async def when_execute_workflow_is_called(self):
        with (
            patch.object(
                self.processor,
                "_capture_pre_rebase_sha",
                new_callable=AsyncMock,
            ),
            patch.object(
                self.processor,
                "_wait_for_rebase",
                new_callable=AsyncMock,
                return_value=ProcessingResult.TIMEOUT,
            ),
        ):
            self.result = await self.processor._execute_workflow(self.ctx)

    def then_result_is_timeout(self):
        assert self.result == ProcessingResult.TIMEOUT
