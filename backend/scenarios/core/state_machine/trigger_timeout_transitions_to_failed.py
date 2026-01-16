"""Test trigger timeout transitions to failed."""

import vedro
from scenarios.library import QueueState
from scenarios.contexts.state_machine_helpers import (
    create_mock_notifier,
    create_mock_queue_manager,
    create_state_machine,
)


class Scenario(vedro.Scenario):
    subject = "trigger timeout transitions to failed"

    async def given_state_machine_in_testing(self):
        self.notifier = create_mock_notifier()
        self.queue_manager = create_mock_queue_manager()
        self.sm = await create_state_machine(
            self.notifier,
            self.queue_manager,
            start_value=QueueState.TESTING,
        )

    async def when_timeout_is_triggered(self):
        await self.sm.trigger_timeout(max_wait_hours=2)

    def then_it_should_be_in_failed_state(self):
        assert self.sm.current_state.id == "failed"
