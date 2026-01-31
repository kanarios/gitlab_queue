"""Test notify_affected_mrs_after_hotfix_added notifies with hotfix context."""

import vedro

from .._helpers import (
    MockQueueItem,
    create_mock_notifier,
    create_mock_queue_manager,
    create_position_notifier,
)


class Scenario(vedro.Scenario):
    subject = "notify_affected_mrs_after_hotfix_added notifies with hotfix context"

    async def given_positions_before_hotfix_added(self):
        self.hotfix_mr_iid = 100
        self.positions_before = {101: 1, 102: 2}
        queue_items_after = [
            MockQueueItem(mr_iid=100, state="queued", is_hotfix=True),
            MockQueueItem(mr_iid=101, state="queued"),
            MockQueueItem(mr_iid=102, state="queued"),
        ]
        self.notifier = create_mock_notifier()
        self.queue_manager = create_mock_queue_manager(queue_items_after)
        self.position_notifier = create_position_notifier(
            notifier=self.notifier,
            queue_manager=self.queue_manager,
        )

    async def when_notify_after_hotfix_is_called(self):
        await self.position_notifier.notify_affected_mrs_after_hotfix_added(
            hotfix_mr_iid=self.hotfix_mr_iid,
            positions_before=self.positions_before,
        )

    def then_affected_mrs_are_notified(self):
        assert self.notifier.notify.call_count == 2

    def and_hotfix_mr_is_not_notified(self):
        calls = self.notifier.notify.call_args_list
        # Extract mr_iid: check kwargs first, fall back to positional args
        notified_iids = [
            call.kwargs.get("mr_iid") or call.args[0] for call in calls
        ]
        assert self.hotfix_mr_iid not in notified_iids

    def and_positions_shifted_down_by_one(self):
        calls = self.notifier.notify.call_args_list
        notifications = [
            (c.kwargs.get("mr_iid") or c.args[0], c.kwargs["position"], c.kwargs["old_position"])
            for c in calls
        ]
        expected = {(101, 2, 1), (102, 3, 2)}
        assert set(notifications) == expected
