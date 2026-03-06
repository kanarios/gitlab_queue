"""Test notify_position_changed calls notifier when position changed."""

from datetime import UTC, datetime, timedelta

import vedro
from scenarios.contexts.state_machine_helpers import (
    create_mock_notifier,
    create_state_machine,
)
from scenarios.fakes import FakeQueueManager

from gitlab_queue.models.queue_item import QueueItem


class Scenario(vedro.Scenario):
    subject = "notify_position_changed calls notifier when position changed"

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

    async def when_notify_position_changed_is_called_with_old_position_3(self):
        await self.sm.notify_position_changed(old_position=3)

    def then_it_should_stay_in_queued_state(self):
        assert self.sm.current_state.id == "queued"

    def and_notifier_should_be_called_with_position_changed_template(self):
        """
        Assert that notifier.notify was awaited with the MR IID 123 and the "position_changed" template.

        Verifies that the notifier's notify method was awaited and that its first positional argument is 123 (MR IID) and its second positional argument is "position_changed".
        """
        # Find the position_changed call (skip initial state notification)
        position_calls = [c for c in self.notifier.notify_calls if c["status"] == "position_changed"]
        assert len(position_calls) > 0
        assert position_calls[0]["mr_iid"] == 123
        assert position_calls[0]["status"] == "position_changed"

    def and_notify_should_include_old_and_new_position(self):
        position_calls = [c for c in self.notifier.notify_calls if c["status"] == "position_changed"]
        assert position_calls[0]["position"] == 2
        assert position_calls[0]["old_position"] == 3
