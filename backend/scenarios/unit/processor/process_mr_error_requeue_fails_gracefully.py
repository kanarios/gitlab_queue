"""Test scenario: failed re-queue after error does not crash processor.

When _process_mr encounters an error AND the subsequent reset to "queued" also
fails (e.g. DB is down), the processor should still return ERROR gracefully.
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
    subject = "failed re-queue after error does not crash processor"

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

    def given_reset_to_queued_also_fails(self):
        self.sm_factory.state_machine.trigger_errors["reset_to_queued"] = RuntimeError("DB down")

    async def when_process_mr_is_called(self):
        self.result = await self.processor._process_mr(self.queue_item)

    def then_result_is_error(self):
        assert self.result == ProcessingResult.ERROR
