"""Test creating state machine with custom start state."""

import vedro
from scenarios.library import QueueState
from scenarios.contexts.state_machine_helpers import (
    create_mock_notifier,
    create_mock_queue_manager,
    create_state_machine,
)


class Scenario(vedro.Scenario):
    subject = "create state machine with custom start state"

    def given_dependencies(self):
        self.notifier = create_mock_notifier()
        self.queue_manager = create_mock_queue_manager()

    async def when_state_machine_is_created_with_start_value(self):
        self.sm = await create_state_machine(
            self.notifier,
            self.queue_manager,
            start_value=QueueState.TESTING,
        )

    def then_it_should_start_in_specified_state(self):
        assert self.sm.current_state.id == "testing"
