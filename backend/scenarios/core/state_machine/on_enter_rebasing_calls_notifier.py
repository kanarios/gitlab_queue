"""Test on_enter_rebasing calls notifier with correct template."""

import vedro
from scenarios.contexts.state_machine_helpers import (
    create_mock_notifier,
    create_mock_queue_manager,
    create_state_machine,
)


class Scenario(vedro.Scenario):
    subject = "on_enter_rebasing calls notifier with correct template"

    async def given_state_machine_in_queued(self):
        self.notifier = create_mock_notifier()
        self.queue_manager = create_mock_queue_manager()
        self.sm = await create_state_machine(
            self.notifier,
            self.queue_manager,
            mr_iid=123,
            target_branch="main",
        )

    async def when_start_processing_is_triggered(self):
        """
        Trigger the scenario's state machine to start processing.
        
        Invokes the state machine's start processing action to advance its workflow.
        """
        await self.sm.trigger_start_processing()

    def then_notifier_should_be_called_with_rebasing_template(self):
        """
        Verify that notifier.notify was awaited and invoked with mr_iid 123 and template "rebasing".
        
        Asserts the notify coroutine was awaited and that its first positional argument equals 123 (mr_iid) and its second positional argument equals "rebasing" (template).
        """
        self.notifier.notify.assert_awaited()
        call_args = self.notifier.notify.call_args
        assert call_args[0][0] == 123  # mr_iid
        assert call_args[0][1] == "rebasing"  # template

    def and_notify_should_include_target_branch(self):
        call_kwargs = self.notifier.notify.call_args[1]
        assert call_kwargs.get("target_branch") == "main"
