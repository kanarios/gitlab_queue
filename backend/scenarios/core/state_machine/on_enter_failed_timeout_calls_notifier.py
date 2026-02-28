"""Test on_enter_failed calls notifier with timeout template."""

import vedro
from scenarios.contexts.state_machine_helpers import (
    create_mock_notifier,
    create_mock_queue_manager,
    create_state_machine,
)
from scenarios.library import QueueState


class Scenario(vedro.Scenario):
    subject = "on_enter_failed calls notifier with timeout template"

    async def given_state_machine_in_testing(self):
        self.notifier = create_mock_notifier()
        self.queue_manager = create_mock_queue_manager()
        self.sm = await create_state_machine(
            self.notifier,
            self.queue_manager,
            mr_iid=123,
            start_value=QueueState.TESTING,
        )

    async def when_timeout_is_triggered(self):
        """
        Trigger a timeout on the scenario's state machine using a 4-hour maximum wait.

        This causes the scenario's state machine (`self.sm`) to handle a timeout event with max_wait_hours set to 4.
        """
        await self.sm.trigger_timeout(max_wait_hours=4)

    def then_notifier_should_be_called_with_timeout_template(self):
        """
        Asserts that the notifier's notify coroutine was awaited and invoked with the timeout template for mr_iid 123.

        Verifies that notify was awaited, that the first positional argument equals 123 (mr_iid) and the second positional argument equals "timeout" (template).
        """
        self.notifier.notify.assert_awaited()
        call_args = self.notifier.notify.call_args
        assert call_args[0][0] == 123  # mr_iid
        assert call_args[0][1] == "timeout"  # template

    def and_notify_should_include_max_wait(self):
        call_kwargs = self.notifier.notify.call_args[1]
        assert call_kwargs.get("max_wait") == 4
