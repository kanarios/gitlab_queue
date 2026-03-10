"""Test: error during processing increments processing_attempts counter."""

from __future__ import annotations

import vedro

from gitlab_queue.core.processor import ProcessingResult
from scenarios.fakes import (
    FakeCurrentState,
    FakeGitLabClient,
    FakeStateMachine,
    FakeStateMachineFactory,
)
from scenarios.unit.processor._helpers import (
    create_mock_processor,
    create_test_queue_item,
)


class Scenario(vedro.Scenario):
    subject = "error during processing increments processing_attempts"

    def given_gitlab_client_that_errors(self):
        self.gitlab_client = FakeGitLabClient(
            rebase_mr_error=RuntimeError("transient error"),
        )

    def given_processor(self):
        sm = FakeStateMachine(current_state=FakeCurrentState(id="queued"))
        self.sm_factory = FakeStateMachineFactory(state_machine=sm)
        self.processor = create_mock_processor(
            gitlab_client=self.gitlab_client,
            state_machine_factory=self.sm_factory,
        )

    def given_mr_in_queue(self):
        self.queue_item = create_test_queue_item(mr_iid=42, state="queued", processing_attempts=0)
        self.processor.queue_manager.add_item(self.queue_item)

    async def when_process_mr_is_called(self):
        self.result = await self.processor._process_mr(self.queue_item)

    def then_result_is_error(self):
        assert self.result == ProcessingResult.ERROR

    def then_processing_attempts_incremented(self):
        attempts_calls = [c for c in self.processor.queue_manager.update_state_calls if "processing_attempts" in c]
        assert len(attempts_calls) >= 1
        assert attempts_calls[-1]["processing_attempts"] == 1
