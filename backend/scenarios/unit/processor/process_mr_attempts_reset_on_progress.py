"""Test: processing_attempts reset to 0 on successful transition to testing.

When _execute_workflow reaches the testing state, it should reset
processing_attempts to 0 via update_mr_state.
"""

from __future__ import annotations

import vedro

from scenarios.fakes import (
    FakeCurrentState,
    FakeQueueManager,
    FakeStateMachine,
    FakeStateMachineFactory,
)
from scenarios.unit.processor._helpers import (
    create_mock_processor,
    create_test_queue_item,
)


class Scenario(vedro.Scenario):
    subject = "processing_attempts reset to 0 on successful transition to testing"

    def given_processor_resuming_from_testing(self):
        sm = FakeStateMachine(current_state=FakeCurrentState(id="testing"))
        self.sm_factory = FakeStateMachineFactory(state_machine=sm)
        self.queue_manager = FakeQueueManager()
        self.processor = create_mock_processor(
            state_machine_factory=self.sm_factory,
            queue_manager=self.queue_manager,
        )
        # Signal shutdown so _wait_for_pipeline exits immediately
        # (reset happens BEFORE pipeline wait in _execute_workflow)
        self.processor.request_shutdown()

    def given_mr_with_previous_attempts(self):
        self.queue_item = create_test_queue_item(
            mr_iid=42,
            state="testing",
            processing_attempts=2,
        )
        self.queue_manager.add_item(self.queue_item)

    async def when_process_mr_is_called(self):
        self.result = await self.processor._process_mr(self.queue_item)

    def then_processing_attempts_were_reset(self):
        reset_calls = [c for c in self.queue_manager.update_state_calls if c.get("processing_attempts") == 0]
        assert len(reset_calls) >= 1, (
            f"Expected update_mr_state with processing_attempts=0, got: {self.queue_manager.update_state_calls}"
        )
