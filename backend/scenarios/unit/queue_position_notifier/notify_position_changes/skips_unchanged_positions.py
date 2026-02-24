"""Test _notify_position_changes skips unchanged positions."""

import vedro

from .._helpers import (
    MockQueueItem,
    create_mock_notifier,
    create_mock_queue_manager,
    create_position_notifier,
)


class Scenario(vedro.Scenario):
    subject = "_notify_position_changes skips MRs with unchanged position"

    async def given_mr_with_same_position_before_and_after(self):
        self.positions_before = {101: 1, 102: 2}
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
        # old_total=2 matches new total (2 items), so no total change either
        self.notified_count = await self.position_notifier._notify_position_changes(
            excluded_mr_iid=999,
            positions_before=self.positions_before,
            old_total=len(self.positions_before),
            log_context="",
        )

    def then_no_notifications_are_sent(self):
        self.notifier.notify.assert_not_awaited()

    def and_notified_count_is_0(self):
        assert self.notified_count == 0
