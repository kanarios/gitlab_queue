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

    def given_positions_before_and_after_change(self):
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
        """
        Call the position notifier to notify MRs about position changes and store the result.

        This coroutine invokes self.position_notifier._notify_position_changes with an excluded MR IID of 999, the previously recorded positions, the previous total count, and an empty log context. Sets self.notified_count to the number of notifications that were sent.
        """
        self.notified_count = await self.position_notifier._notify_position_changes(
            99999,
            excluded_mr_iid=999,
            positions_before=self.positions_before,
            old_total=len(self.positions_before),
            log_context="",
        )

    def then_two_notifications_are_sent(self):
        assert self.notifier.notify.call_count == 2

    def and_notified_count_is_2(self):
        assert self.notified_count == 2

    def and_notifications_use_position_changed_template(self):
        calls = self.notifier.notify.call_args_list
        statuses = [c.kwargs.get("status", c.args[1] if len(c.args) > 1 else None) for c in calls]
        assert all(s == "position_changed" for s in statuses)
