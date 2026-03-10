"""Test: error recovery handles MR already removed from queue."""

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
    subject = "error recovery when MR already removed from queue"

    def given_gitlab_client_that_errors(self):
        self.gitlab_client = FakeGitLabClient(
            rebase_mr_error=RuntimeError("transient error"),
        )

    def given_processor_with_empty_queue(self):
        sm = FakeStateMachine(current_state=FakeCurrentState(id="queued"))
        self.sm_factory = FakeStateMachineFactory(state_machine=sm)
        self.processor = create_mock_processor(
            gitlab_client=self.gitlab_client,
            state_machine_factory=self.sm_factory,
        )
        # Do NOT add item to queue_manager — get_queue_item will return None

    def given_queue_item_for_processing(self):
        self.queue_item = create_test_queue_item(mr_iid=42, state="queued")

    async def when_process_mr_is_called(self):
        self.result = await self.processor._process_mr(self.queue_item)

    def then_result_is_error(self):
        assert self.result == ProcessingResult.ERROR

    def then_update_mr_state_not_called(self):
        update_calls = self.processor.queue_manager.update_state_calls
        assert len(update_calls) == 0
