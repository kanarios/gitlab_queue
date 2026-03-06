"""Test _execute_workflow returns early when _wait_for_pipeline fails in testing state.

Line 347: return result when _wait_for_pipeline returns non-SUCCESS in the testing path.
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
    subject = "execute workflow returns early when wait_for_pipeline fails in testing state"

    def given_processor_with_testing_mr_and_pipeline_failure(self):
        self.processor = create_mock_processor()
        self.mock_sm = create_mock_state_machine()
        self.mock_sm.current_state.id = "testing"
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.mock_sm)

    async def when_execute_workflow_is_called(self):
        with patch.object(
            self.processor,
            "_wait_for_pipeline",
            new_callable=AsyncMock,
            return_value=ProcessingResult.PIPELINE_FAILED,
        ):
            self.result = await self.processor._execute_workflow(self.ctx)

    def then_result_is_pipeline_failed(self):
        assert self.result == ProcessingResult.PIPELINE_FAILED
