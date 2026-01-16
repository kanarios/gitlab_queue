"""Test on_enter_removed calls notifier with removed_label template."""

import vedro
from scenarios.contexts.state_machine_helpers import (
    create_mock_notifier,
    create_mock_queue_manager,
    create_state_machine,
)


class Scenario(vedro.Scenario):
    subject = "on_enter_removed calls notifier with removed_label template"

    async def given_state_machine_in_queued(self):
        self.notifier = create_mock_notifier()
        self.queue_manager = create_mock_queue_manager()
        self.sm = await create_state_machine(
            self.notifier,
            self.queue_manager,
            mr_iid=123,
        )

    async def when_mark_removed_is_triggered_with_label_removed(self):
        await self.sm.trigger_mark_removed(reason="label_removed")

    def then_notifier_should_be_called_with_removed_label_template(self):
        self.notifier.notify.assert_called()
        call_args = self.notifier.notify.call_args
        assert call_args[0][0] == 123  # mr_iid
        assert call_args[0][1] == "removed_label"  # template

    def and_notify_should_include_position(self):
        call_kwargs = self.notifier.notify.call_args[1]
        assert "position" in call_kwargs
