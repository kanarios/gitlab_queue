"""Test creating state machine with initial queued state."""

import vedro
from scenarios.contexts.state_machine_helpers import (
    create_mock_notifier,
    create_mock_queue_manager,
    create_state_machine,
)


class Scenario(vedro.Scenario):
    subject = "create state machine with initial queued state"

    def given_dependencies(self):
        self.notifier = create_mock_notifier()
        self.queue_manager = create_mock_queue_manager()

    async def when_state_machine_is_created(self):
        self.sm = await create_state_machine(
            self.notifier,
            self.queue_manager,
        )

    def then_it_should_start_in_queued_state(self):
        assert self.sm.current_state.id == "queued"
