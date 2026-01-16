"""Test merging state can transition to merged."""

import vedro
from scenarios.contexts.state_machine_helpers import (
    create_mock_notifier,
    create_mock_queue_manager,
    create_state_machine,
)
from scenarios.library import QueueState


class Scenario(vedro.Scenario):
    subject = "merging state can transition to merged"

    async def given_state_machine_in_merging(self):
        self.notifier = create_mock_notifier()
        self.queue_manager = create_mock_queue_manager()
        self.sm = await create_state_machine(
            self.notifier,
            self.queue_manager,
            start_value=QueueState.MERGING,
        )

    async def when_merge_success_is_triggered(self):
        await self.sm.trigger_merge_success()

    def then_it_should_be_in_merged_state(self):
        assert self.sm.current_state.id == "merged"
