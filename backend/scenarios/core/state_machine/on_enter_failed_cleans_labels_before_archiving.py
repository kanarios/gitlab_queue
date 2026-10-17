"""The durable completion row must survive until mandatory label cleanup succeeds."""

from datetime import UTC, datetime

import vedro
from scenarios.contexts.state_machine_helpers import (
    create_state_machine,
)
from scenarios.fakes import FakeNotifier, FakeQueueManager
from scenarios.library import QueueState

from gitlab_queue.models.queue_item import QueueItem


class Scenario(vedro.Scenario):
    subject = "on_enter_failed cleans up labels before archiving the owned completion"

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

    def then_cleanup_should_finish_before_the_owned_row_is_archived(self):
        assert self.call_order == ["remove_queue_label", "complete_mr"]
