"""Test _execute_workflow returns early when _wait_for_pipeline fails in testing state.

Line 347: return result when _wait_for_pipeline returns non-SUCCESS in the testing path.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import vedro

from gitlab_queue.core.types import ProcessingContext, ProcessingResult

from .._helpers import (
    create_mock_processor,
    create_mock_state_machine,
    create_processing_context,
)


@dataclass
class FakePipelineHandler:
    wait_for_pipeline_result: ProcessingResult = ProcessingResult.SUCCESS
    wait_for_pipeline_calls: list[ProcessingContext] = field(default_factory=list)

    async def wait_for_pipeline(self, ctx: ProcessingContext) -> ProcessingResult:
        self.wait_for_pipeline_calls.append(ctx)
        return self.wait_for_pipeline_result


class Scenario(vedro.Scenario):
    subject = "execute workflow returns early when wait_for_pipeline fails in testing state"

    def given_processor_with_testing_mr_and_pipeline_failure(self):
        self.processor = create_mock_processor()
        self.mock_sm = create_mock_state_machine()
        self.mock_sm.current_state.id = "testing"
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.mock_sm)

        # Inject fake pipeline handler that returns PIPELINE_FAILED
        self.processor._ph = FakePipelineHandler(wait_for_pipeline_result=ProcessingResult.PIPELINE_FAILED)

    async def when_execute_workflow_is_called(self):
        self.result = await self.processor._execute_workflow(self.ctx)

    def then_result_is_pipeline_failed(self):
        assert self.result == ProcessingResult.PIPELINE_FAILED
