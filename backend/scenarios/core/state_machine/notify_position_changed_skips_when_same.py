"""Test notify_position_changed skips notification when position unchanged."""

from datetime import UTC, datetime, timedelta

import vedro
from scenarios.contexts.state_machine_helpers import (
    create_mock_notifier,
    create_state_machine,
)
from scenarios.fakes import FakeQueueManager

from gitlab_queue.models.queue_item import QueueItem


class Scenario(vedro.Scenario):
    subject = "notify_position_changed skips notification when position unchanged"

    async def given_state_machine_in_queued(self):
        self.notifier = create_mock_notifier()
        self.queue_manager = FakeQueueManager()
        now = datetime.now(UTC)
        # Add a dummy item first so mr_iid=123 is at position 2
        self.queue_manager.add_item(
            QueueItem(
                mr_iid=999,
                title="First MR",
                author_name="Test",
                author_username="test",
                target_branch="master",
                state="queued",
                queued_at=now - timedelta(minutes=1),
            )
        )
        self.queue_manager.add_item(
            QueueItem(
                mr_iid=123,
                title="Test MR",
                author_name="Test",
                author_username="test",
                target_branch="master",
                state="queued",
                queued_at=now,
            )
        )
        self.sm = await create_state_machine(
            self.notifier,
            self.queue_manager,
            mr_iid=123,
        )
        # Clear calls after initial state notification
        self.notifier.notify_calls.clear()

    async def when_notify_position_changed_is_called_with_same_position(self):
        await self.sm.notify_position_changed(old_position=2)

    def then_notifier_should_not_be_called(self):
        assert len(self.notifier.notify_calls) == 0
