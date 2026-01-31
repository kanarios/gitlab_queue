"""Test _notify_position_changes notifies MRs with changed position."""

import vedro

from .._helpers import (
    MockQueueItem,
    create_mock_notifier,
    create_mock_queue_manager,
    create_position_notifier,
)


class Scenario(vedro.Scenario):
    subject = "_notify_position_changes notifies MRs with changed position"

    async def given_positions_before_and_after_change(self):
        self.positions_before = {101: 2, 102: 3}
        queue_items_after = [
            MockQueueItem(mr_iid=101, state="queued"),
            MockQueueItem(mr_iid=102, state="queued"),
        ]
        self.notifier = create_mock_notifier()
        self.queue_manager = create_mock_queue_manager(queue_items_after)
        self.position_notifier = create_position_notifier(
            notifier=self.notifier,
            queue_manager=self.queue_manager,
        )

    async def when_notify_position_changes_is_called(self):
        self.notified_count = await self.position_notifier._notify_position_changes(
            excluded_mr_iid=999,
            positions_before=self.positions_before,
            log_context="",
        )

    def then_two_notifications_are_sent(self):
        assert self.notifier.notify.call_count == 2

    def and_notified_count_is_2(self):
        assert self.notified_count == 2

    def and_notifications_use_position_changed_template(self):
        calls = self.notifier.notify.call_args_list
        statuses = [c.kwargs.get("status") or c.args[1] for c in calls]
        assert all(s == "position_changed" for s in statuses)
