"""Test _notify_position_changes uses total_changed_hotfix template."""

import vedro

from .._helpers import (
    MockQueueItem,
    create_mock_notifier,
    create_mock_queue_manager,
    create_position_notifier,
)


class Scenario(vedro.Scenario):
    subject = "_notify_position_changes uses total_changed_hotfix template when only total changes and is_hotfix"

    def given_mr_with_same_position_but_different_total_and_hotfix(self):
        self.positions_before = {101: 1}
        self.old_total = 1
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

    async def when_notify_position_changes_is_called_with_hotfix(self):
        self.notified_count = await self.position_notifier._notify_position_changes(
            excluded_mr_iid=102,
            positions_before=self.positions_before,
            old_total=self.old_total,
            log_context=" due to hotfix",
            is_hotfix=True,
        )

    def then_one_notification_is_sent(self):
        assert self.notifier.notify.call_count == 1

    def and_notified_count_is_1(self):
        assert self.notified_count == 1

    def and_notification_uses_total_changed_hotfix_template(self):
        call = self.notifier.notify.call_args_list[0]
        template = call.args[1]
        assert template == "total_changed_hotfix"

    def and_old_total_is_passed_in_kwargs(self):
        call = self.notifier.notify.call_args_list[0]
        assert call.kwargs["old_total"] == 1
