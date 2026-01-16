"""Test testing state can transition to merging."""

import vedro
from scenarios.contexts.state_machine_helpers import (
    create_mock_notifier,
    create_mock_queue_manager,
    create_state_machine,
)
from scenarios.library import QueueState


class Scenario(vedro.Scenario):
    subject = "testing state can transition to merging"

    async def given_state_machine_in_testing(self):
        self.notifier = create_mock_notifier()
        self.queue_manager = create_mock_queue_manager()
        self.sm = await create_state_machine(
            self.notifier,
            self.queue_manager,
            start_value=QueueState.TESTING,
        )

    async def when_pipeline_success_is_triggered(self):
        await self.sm.trigger_pipeline_success()

    def then_it_should_be_in_merging_state(self):
        assert self.sm.current_state.id == "merging"
