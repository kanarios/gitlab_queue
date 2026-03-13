"""Test on_enter_removed from merging state includes previous_state in notify."""

import vedro
from scenarios.contexts.state_machine_helpers import (
    create_mock_notifier,
    create_mock_queue_manager,
    create_state_machine,
)
from scenarios.library import QueueState


class Scenario(vedro.Scenario):
    subject = "on_enter_removed from merging includes previous_state=merging"

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
        await self.sm.trigger_mark_removed(reason="label_removed")

    def then_notifier_should_include_previous_state_merging(self):
        call_args = self.notifier.notify_calls[0]
        assert call_args["status"] == "removed_label"
        assert call_args["previous_state"] == "merging"
