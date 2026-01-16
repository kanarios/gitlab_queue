"""Test merging state can transition to removed."""

import vedro
from scenarios.contexts.state_machine_helpers import (
    create_mock_notifier,
    create_mock_queue_manager,
    create_state_machine,
)
from scenarios.library import QueueState


class Scenario(vedro.Scenario):
    subject = "merging state can transition to removed"

    async def given_state_machine_in_merging(self):
        self.notifier = create_mock_notifier()
        self.queue_manager = create_mock_queue_manager()
        self.sm = await create_state_machine(
            self.notifier,
            self.queue_manager,
            mr_iid=123,
            start_value=QueueState.MERGING,
        )

    async def when_mark_removed_is_triggered(self):
        await self.sm.trigger_mark_removed(reason="closed")

    def then_it_should_be_in_removed_state(self):
        assert self.sm.current_state.id == "removed"
