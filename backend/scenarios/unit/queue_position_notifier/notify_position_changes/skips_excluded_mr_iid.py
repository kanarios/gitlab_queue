"""Test _notify_position_changes skips excluded mr_iid."""

import vedro

from .._helpers import (
    MockQueueItem,
    create_mock_notifier,
    create_mock_queue_manager,
    create_position_notifier,
)


class Scenario(vedro.Scenario):
    subject = "_notify_position_changes skips excluded mr_iid"

    async def given_excluded_mr_with_changed_position(self):
        self.excluded_mr_iid = 101
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

    async def when_notify_position_changes_is_called_with_excluded_mr(self):
        self.notified_count = await self.position_notifier._notify_position_changes(
            excluded_mr_iid=self.excluded_mr_iid,
            positions_before=self.positions_before,
            log_context="",
        )

    def then_only_one_notification_is_sent(self):
        assert self.notifier.notify.call_count == 1

    def and_notification_is_for_non_excluded_mr(self):
        call_args = self.notifier.notify.call_args
        assert call_args[0][0] == 102

    def and_notified_count_is_1(self):
        assert self.notified_count == 1
