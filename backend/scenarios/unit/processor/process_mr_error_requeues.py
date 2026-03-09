"""Test scenario: unexpected error during processing resets MR to queued.

When _process_mr encounters an unexpected exception, the MR state should be
reset to "queued" so it can be retried, instead of staying stuck in "rebasing".
"""

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
    subject = "unexpected error during processing resets MR to queued"

    def given_gitlab_client_that_errors_on_rebase(self):
        self.gitlab_client = FakeGitLabClient(
            rebase_mr_error=RuntimeError("unexpected"),
        )

    def given_processor_with_failing_workflow(self):
        sm = FakeStateMachine(current_state=FakeCurrentState(id="queued"))
        self.sm_factory = FakeStateMachineFactory(state_machine=sm)
        self.processor = create_mock_processor(
            gitlab_client=self.gitlab_client,
            state_machine_factory=self.sm_factory,
        )

    def given_mr_in_queue(self):
        self.queue_item = create_test_queue_item(mr_iid=42, state="queued")
        self.processor.queue_manager.add_item(self.queue_item)

    async def when_process_mr_is_called(self):
        self.result = await self.processor._process_mr(self.queue_item)

    def then_result_is_error(self):
        assert self.result == ProcessingResult.ERROR

    def then_mr_state_was_reset_to_queued(self):
        sm = self.sm_factory.state_machine
        assert len(sm.reset_to_queued_calls) == 1
        assert sm.reset_to_queued_calls[0]["error_message"] == "unexpected"
