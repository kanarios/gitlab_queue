"""Test _execute_workflow returns early when _wait_for_rebase fails in rebasing state.

Line 340: return result when _wait_for_rebase returns non-SUCCESS in the rebasing path.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import vedro

from gitlab_queue.core.types import ProcessingContext, ProcessingResult

from .._helpers import (
    create_mock_processor,
    create_mock_state_machine,
    create_processing_context,
)


@dataclass
class FakeRebaseHandler:
    wait_for_rebase_result: ProcessingResult = ProcessingResult.SUCCESS
    capture_pre_rebase_sha_calls: list[Any] = field(default_factory=list)
    wait_for_rebase_calls: list[Any] = field(default_factory=list)

    async def capture_pre_rebase_sha(self, ctx: ProcessingContext) -> str:
        self.capture_pre_rebase_sha_calls.append(ctx)
        return "sha"

    async def wait_for_rebase(self, ctx: ProcessingContext) -> ProcessingResult:
        self.wait_for_rebase_calls.append(ctx)
        return self.wait_for_rebase_result


class Scenario(vedro.Scenario):
    subject = "execute workflow returns early when wait_for_rebase fails in rebasing state"

    def given_processor_with_rebasing_mr_and_timeout(self):
        self.processor = create_mock_processor()
        self.mock_sm = create_mock_state_machine()
        self.mock_sm.current_state.id = "rebasing"
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.mock_sm)

        # Inject fake rebase handler that returns TIMEOUT
        self.processor._rh = FakeRebaseHandler(wait_for_rebase_result=ProcessingResult.TIMEOUT)

    async def when_execute_workflow_is_called(self):
        self.result = await self.processor._execute_workflow(self.ctx)

    def then_result_is_timeout(self):
        assert self.result == ProcessingResult.TIMEOUT
