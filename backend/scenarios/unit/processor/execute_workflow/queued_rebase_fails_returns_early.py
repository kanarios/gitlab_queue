"""Test _execute_workflow returns early when _process_rebase fails in queued state.

Line 331: return result when _process_rebase returns non-SUCCESS in the queued path.
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
class FakeRebaseHandler:
    process_rebase_result: ProcessingResult = ProcessingResult.SUCCESS
    process_rebase_calls: list[ProcessingContext] = field(default_factory=list)

    async def process_rebase(self, ctx: ProcessingContext) -> ProcessingResult:
        self.process_rebase_calls.append(ctx)
        return self.process_rebase_result


class Scenario(vedro.Scenario):
    subject = "execute workflow returns early when rebase fails in queued state"

    def given_processor_with_queued_mr_and_failing_rebase(self):
        self.processor = create_mock_processor(_rh=FakeRebaseHandler(process_rebase_result=ProcessingResult.CONFLICT))
        self.mock_sm = create_mock_state_machine()
        self.mock_sm.current_state.id = "queued"
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.mock_sm)

    async def when_execute_workflow_is_called(self):
        self.result = await self.processor._execute_workflow(self.ctx)

    def then_result_is_conflict(self):
        assert self.result == ProcessingResult.CONFLICT

    def and_trigger_start_processing_was_called(self):
        assert len(self.mock_sm.start_processing_calls) == 1
