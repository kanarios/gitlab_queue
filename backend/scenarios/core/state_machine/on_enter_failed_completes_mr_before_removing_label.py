"""Test that on_enter_failed calls complete_mr BEFORE remove_queue_label.

This prevents a race condition where the webhook from label removal
could arrive before the MR is completed in the queue.
"""

import vedro
from scenarios.contexts.state_machine_helpers import (
    create_mock_notifier,
    create_mock_queue_manager,
    create_state_machine,
)
from scenarios.library import QueueState


class Scenario(vedro.Scenario):
    subject = "on_enter_failed completes MR before removing queue label"

    async def given_state_machine_in_rebasing(self):
        self.call_order: list[str] = []
        self.notifier = create_mock_notifier()
        self.queue_manager = create_mock_queue_manager()

        # Patch to record call order
        original_complete = self.queue_manager.complete_mr
        original_remove = self.notifier.remove_queue_label

        async def recording_complete(*args, **kwargs):
            self.call_order.append("complete_mr")
            return await original_complete(*args, **kwargs)

        async def recording_remove(*args, **kwargs):
            self.call_order.append("remove_queue_label")
            return await original_remove(*args, **kwargs)

        self.queue_manager.complete_mr = recording_complete
        self.notifier.remove_queue_label = recording_remove

        self.sm = await create_state_machine(
            self.notifier,
            self.queue_manager,
            mr_iid=123,
            start_value=QueueState.REBASING,
        )

    async def when_rebase_failed_is_triggered(self):
        await self.sm.trigger_rebase_failed(
            conflicted_files=["src/main.py"],
            error_message="Merge conflict",
        )

    def then_complete_mr_should_be_called_before_remove_label(self):
        assert self.call_order == ["complete_mr", "remove_queue_label"]
