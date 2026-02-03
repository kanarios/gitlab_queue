"""Test _notify_position_changes uses position_changed_hotfix template."""

import vedro

from .._helpers import (
    MockQueueItem,
    create_mock_notifier,
    create_mock_queue_manager,
    create_position_notifier,
)


class Scenario(vedro.Scenario):
    subject = "_notify_position_changes uses position_changed_hotfix template when position changes and is_hotfix"

    def given_mrs_with_positions_shifted_by_hotfix(self):
        self.positions_before = {101: 1, 102: 2}
        self.old_total = 2
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

    async def when_notify_position_changes_is_called_with_hotfix(self):
        self.notified_count = await self.position_notifier._notify_position_changes(
            excluded_mr_iid=100,
            positions_before=self.positions_before,
            old_total=self.old_total,
            log_context=" due to hotfix",
            is_hotfix=True,
        )

    def then_two_notifications_are_sent(self):
        assert self.notifier.notify.call_count == 2

    def and_notified_count_is_2(self):
        assert self.notified_count == 2

    def and_all_notifications_use_position_changed_hotfix_template(self):
        calls = self.notifier.notify.call_args_list
        templates = [c.args[1] for c in calls]
        assert all(t == "position_changed_hotfix" for t in templates)

    def and_positions_shifted_down_by_one(self):
        calls = self.notifier.notify.call_args_list
        notifications = [(c.args[0], c.kwargs["position"], c.kwargs["old_position"]) for c in calls]
        expected = {(101, 2, 1), (102, 3, 2)}
        assert set(notifications) == expected
