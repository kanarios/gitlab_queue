"""Test notify_stale_warning calls notifier with stale_warning template."""

import vedro
from scenarios.contexts.state_machine_helpers import (
    create_mock_notifier,
    create_mock_queue_manager,
    create_state_machine,
)


class Scenario(vedro.Scenario):
    subject = "notify_stale_warning calls notifier with stale_warning template"

    async def given_state_machine_in_queued(self):
        self.notifier = create_mock_notifier()
        self.queue_manager = create_mock_queue_manager()
        self.sm = await create_state_machine(
            self.notifier,
            self.queue_manager,
            mr_iid=123,
        )

    async def when_notify_stale_warning_is_called(self):
        await self.sm.notify_stale_warning(warning_hours=12)

    def then_it_should_stay_in_queued_state(self):
        assert self.sm.current_state.id == "queued"

    def and_notifier_should_be_called_with_stale_warning_template(self):
        self.notifier.notify.assert_called()
        call_args = self.notifier.notify.call_args
        assert call_args[0][0] == 123  # mr_iid
        assert call_args[0][1] == "stale_warning"  # template

    def and_notify_should_include_warning_hours(self):
        call_kwargs = self.notifier.notify.call_args[1]
        assert call_kwargs.get("warning_hours") == 12
