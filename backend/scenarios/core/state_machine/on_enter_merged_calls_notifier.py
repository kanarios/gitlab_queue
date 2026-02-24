"""Test on_enter_merged calls notifier with merged template."""

import vedro
from scenarios.contexts.state_machine_helpers import (
    create_mock_notifier,
    create_mock_queue_manager,
    create_state_machine,
)
from scenarios.library import QueueState


class Scenario(vedro.Scenario):
    subject = "on_enter_merged calls notifier with merged template"

    async def given_state_machine_in_merging(self):
        self.notifier = create_mock_notifier()
        self.queue_manager = create_mock_queue_manager()
        self.sm = await create_state_machine(
            self.notifier,
            self.queue_manager,
            mr_iid=123,
            start_value=QueueState.MERGING,
            target_branch="master",
        )

    async def when_merge_success_is_triggered(self):
        await self.sm.trigger_merge_success()

    def then_notifier_should_be_called_with_merged_template(self):
        self.notifier.notify.assert_awaited()
        call_args = self.notifier.notify.call_args
        assert call_args[0][0] == 123  # mr_iid
        assert call_args[0][1] == "merged"  # template

    def and_notify_should_include_duration_and_target_branch(self):
        call_kwargs = self.notifier.notify.call_args[1]
        assert "duration" in call_kwargs
        assert call_kwargs.get("target_branch") == "master"
