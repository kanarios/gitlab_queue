"""Test on_enter_removed calls notifier with removed_closed template."""

import vedro
from scenarios.contexts.state_machine_helpers import (
    create_mock_notifier,
    create_mock_queue_manager,
    create_state_machine,
)
from scenarios.library import QueueState


class Scenario(vedro.Scenario):
    subject = "on_enter_removed calls notifier with removed_closed template"

    async def given_state_machine_in_testing(self):
        self.notifier = create_mock_notifier()
        self.queue_manager = create_mock_queue_manager()
        self.sm = await create_state_machine(
            self.notifier,
            self.queue_manager,
            mr_iid=123,
            start_value=QueueState.TESTING,
        )

    async def when_mark_removed_is_triggered_with_closed(self):
        await self.sm.trigger_mark_removed(reason="closed")

    def then_notifier_should_be_called_with_removed_closed_template(self):
        self.notifier.notify.assert_called()
        call_args = self.notifier.notify.call_args
        assert call_args[0][0] == 123  # mr_iid
        assert call_args[0][1] == "removed_closed"  # template
