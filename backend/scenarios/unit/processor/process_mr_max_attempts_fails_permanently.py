"""Test: MR exceeding max processing attempts is failed permanently."""

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
    subject = "MR exceeding max processing attempts is failed permanently"

    def given_gitlab_client_that_errors(self):
        self.gitlab_client = FakeGitLabClient(
            rebase_mr_error=RuntimeError("persistent error"),
        )

    def given_processor(self):
        sm = FakeStateMachine(current_state=FakeCurrentState(id="queued"))
        self.sm_factory = FakeStateMachineFactory(state_machine=sm)
        self.processor = create_mock_processor(
            gitlab_client=self.gitlab_client,
            state_machine_factory=self.sm_factory,
        )

    def given_mr_at_max_attempts(self):
        self.queue_item = create_test_queue_item(mr_iid=42, state="queued", processing_attempts=4)
        self.processor.queue_manager.add_item(self.queue_item)

    async def when_process_mr_is_called(self):
        self.result = await self.processor._process_mr(self.queue_item)

    def then_result_is_error(self):
        assert self.result == ProcessingResult.ERROR

    def then_mr_was_failed_via_state_machine(self):
        sm = self.sm_factory.state_machine
        # SM is in "rebasing" state (trigger_start_processing was called),
        # so _fail_mr_permanently should use trigger_rebase_failed
        assert len(sm.rebase_failed_calls) == 1

    def then_mr_not_reset_to_queued(self):
        sm = self.sm_factory.state_machine
        assert len(sm.reset_to_queued_calls) == 0
