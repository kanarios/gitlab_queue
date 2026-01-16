"""Test queued state can transition to rebasing."""

import vedro
from scenarios.contexts.state_machine_helpers import (
    create_mock_notifier,
    create_mock_queue_manager,
    create_state_machine,
)


class Scenario(vedro.Scenario):
    subject = "queued state can transition to rebasing"

    async def given_state_machine_in_queued(self):
        self.notifier = create_mock_notifier()
        self.queue_manager = create_mock_queue_manager()
        self.sm = await create_state_machine(
            self.notifier,
            self.queue_manager,
        )

    async def when_start_processing_is_triggered(self):
        await self.sm.trigger_start_processing()

    def then_it_should_be_in_rebasing_state(self):
        assert self.sm.current_state.id == "rebasing"
