"""Test that on_enter_failed calls complete_mr BEFORE remove_queue_label.

This prevents a race condition where the webhook from label removal
could arrive before the MR is completed in the queue.
"""

from datetime import UTC, datetime

import vedro
from scenarios.contexts.state_machine_helpers import (
    create_state_machine,
)
from scenarios.fakes import FakeNotifier, FakeQueueManager
from scenarios.library import QueueState

from gitlab_queue.models.queue_item import QueueItem


class Scenario(vedro.Scenario):
    subject = "on_enter_failed completes MR before removing queue label"

    async def given_state_machine_in_rebasing(self):
        self.call_order: list[str] = []
        self.notifier = FakeNotifier(call_order_log=self.call_order)
        self.queue_manager = FakeQueueManager(call_order_log=self.call_order)
        self.queue_manager.add_item(
            QueueItem(
                mr_iid=123,
                title="Test MR",
                author_name="Test",
                author_username="test",
                target_branch="master",
                state=QueueState.QUEUED,
                queued_at=datetime.now(UTC),
            )
        )

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
