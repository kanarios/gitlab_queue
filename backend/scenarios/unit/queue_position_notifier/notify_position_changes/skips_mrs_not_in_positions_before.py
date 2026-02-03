"""Test _notify_position_changes skips MRs not in positions_before.

When a new MR is added to the queue, it won't be in positions_before
(since it didn't exist before), so it won't be notified.
However, existing MRs that WERE in positions_before will be notified
if the total changed.
"""

import vedro

from .._helpers import (
    MockQueueItem,
    create_mock_notifier,
    create_mock_queue_manager,
    create_position_notifier,
)


class Scenario(vedro.Scenario):
    subject = "_notify_position_changes skips MRs not in positions_before"

    def given_new_mr_not_in_positions_before(self):
        self.positions_before = {101: 1}
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
            old_total=len(self.positions_before),
            log_context="",
        )

    def then_new_mr_is_not_notified(self):
        calls = self.notifier.notify.call_args_list
        notified_iids = [call.kwargs.get("mr_iid", call.args[0]) for call in calls]
        assert 102 not in notified_iids

    def and_existing_mr_is_notified_about_total_change(self):
        # MR 101 was at position 1 with old_total=1
        # Now it's at position 1 with new_total=2, so it gets notified
        calls = self.notifier.notify.call_args_list
        notified_iids = [call.kwargs.get("mr_iid", call.args[0]) for call in calls]
        assert 101 in notified_iids

    def and_notified_count_is_1(self):
        assert self.notified_count == 1
