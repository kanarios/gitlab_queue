"""Test _execute_workflow returns early when resuming the rebase fails in rebasing state."""

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
    resume_rebase_result: ProcessingResult = ProcessingResult.SUCCESS
    resume_rebase_calls: list[ProcessingContext] = field(default_factory=list)

    async def resume_rebase(self, ctx: ProcessingContext) -> ProcessingResult:
        self.resume_rebase_calls.append(ctx)
        return self.resume_rebase_result


class Scenario(vedro.Scenario):
    subject = "execute workflow returns early when resuming rebase fails in rebasing state"

    def given_processor_with_rebasing_mr_and_timeout(self):
        self.processor = create_mock_processor()
        self.mock_sm = create_mock_state_machine()
        self.mock_sm.current_state.id = "rebasing"
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.mock_sm)

        # Inject fake rebase handler that returns TIMEOUT
        self.processor._rh = FakeRebaseHandler(resume_rebase_result=ProcessingResult.TIMEOUT)

    async def when_execute_workflow_is_called(self):
        self.result = await self.processor._execute_workflow(self.ctx)

    def then_result_is_timeout(self):
        assert self.result == ProcessingResult.TIMEOUT
