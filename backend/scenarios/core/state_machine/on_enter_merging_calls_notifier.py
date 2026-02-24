"""Test on_enter_merging calls notifier with merging template."""

import vedro
from scenarios.contexts.state_machine_helpers import (
    create_mock_notifier,
    create_mock_queue_manager,
    create_state_machine,
)
from scenarios.library import QueueState


class Scenario(vedro.Scenario):
    subject = "on_enter_merging calls notifier with merging template"

    async def given_state_machine_in_testing(self):
        self.notifier = create_mock_notifier()
        self.queue_manager = create_mock_queue_manager()
        self.sm = await create_state_machine(
            self.notifier,
            self.queue_manager,
            mr_iid=123,
            start_value=QueueState.TESTING,
            target_branch="develop",
        )

    async def when_pipeline_success_is_triggered(self):
        await self.sm.trigger_pipeline_success()

    def then_notifier_should_be_called_with_merging_template(self):
        self.notifier.notify.assert_awaited()
        call_args = self.notifier.notify.call_args
        assert call_args[0][0] == 123  # mr_iid
        assert call_args[0][1] == "merging"  # template

    def and_notify_should_include_target_branch(self):
        call_kwargs = self.notifier.notify.call_args[1]
        assert call_kwargs.get("target_branch") == "develop"
