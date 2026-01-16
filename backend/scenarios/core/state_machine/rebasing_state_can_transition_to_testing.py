"""Test rebasing state can transition to testing."""

import vedro
from scenarios.contexts.state_machine_helpers import (
    create_mock_notifier,
    create_mock_queue_manager,
    create_state_machine,
)
from scenarios.library import QueueState


class Scenario(vedro.Scenario):
    subject = "rebasing state can transition to testing"

    async def given_state_machine_in_rebasing(self):
        self.notifier = create_mock_notifier()
        self.queue_manager = create_mock_queue_manager()
        self.sm = await create_state_machine(
            self.notifier,
            self.queue_manager,
            start_value=QueueState.REBASING,
        )

    async def when_rebase_complete_is_triggered(self):
        await self.sm.trigger_rebase_complete(
            pipeline_id=456,
            pipeline_url="https://gitlab.com/pipeline/456",
        )

    def then_it_should_be_in_testing_state(self):
        assert self.sm.current_state.id == "testing"
