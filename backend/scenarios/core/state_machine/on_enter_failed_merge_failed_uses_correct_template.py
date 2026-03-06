"""BUG 2: merge_failed should use merge_failed template, not timeout."""

import vedro
from scenarios.contexts.state_machine_helpers import (
    create_mock_notifier,
    create_mock_queue_manager,
    create_state_machine,
)
from scenarios.library import QueueState


class Scenario(vedro.Scenario):
    subject = "on_enter_failed with merge_failed uses merge_failed template"

    async def given_state_machine_in_merging(self):
        self.notifier = create_mock_notifier()
        self.queue_manager = create_mock_queue_manager()
        self.sm = await create_state_machine(
            self.notifier,
            self.queue_manager,
            mr_iid=123,
            start_value=QueueState.MERGING,
        )

    async def when_merge_failed_is_triggered(self):
        await self.sm.trigger_merge_failed(error_message="Cannot merge")

    def then_notifier_should_use_merge_failed_template(self):
        assert len(self.notifier.notify_calls) == 1
        template = self.notifier.notify_calls[-1]["status"]
        assert template == "merge_failed", f"Expected 'merge_failed' template, got '{template}'"

    def and_template_should_not_be_timeout(self):
        template = self.notifier.notify_calls[-1]["status"]
        assert template != "timeout", "merge_failed should not use timeout template"
