"""Test notify_affected_mrs_after_mr_added notifies existing MRs after regular MR added."""

import vedro

from .._helpers import (
    MockQueueItem,
    create_mock_notifier,
    create_mock_queue_manager,
    create_position_notifier,
)


class Scenario(vedro.Scenario):
    subject = "notify_affected_mrs_after_mr_added notifies existing MRs when regular MR added"

    def given_positions_before_regular_mr_added(self):
        self.added_mr_iid = 103
        self.positions_before = {101: 1, 102: 2}
        self.old_total = 2
        queue_items_after = [
            MockQueueItem(mr_iid=101, state="queued"),
            MockQueueItem(mr_iid=102, state="queued"),
            MockQueueItem(mr_iid=103, state="queued"),
        ]
        self.notifier = create_mock_notifier()
        self.queue_manager = create_mock_queue_manager(queue_items_after)
        self.position_notifier = create_position_notifier(
            notifier=self.notifier,
            queue_manager=self.queue_manager,
        )

    async def when_notify_after_mr_added_is_called(self):
        await self.position_notifier.notify_affected_mrs_after_mr_added(
            added_mr_iid=self.added_mr_iid,
            positions_before=self.positions_before,
            old_total=self.old_total,
            is_hotfix=False,
        )

    def then_existing_mrs_are_notified(self):
        assert self.notifier.notify.call_count == 2

    def and_added_mr_is_not_notified(self):
        calls = self.notifier.notify.call_args_list
        notified_iids = [c.args[0] for c in calls]
        assert self.added_mr_iid not in notified_iids

    def and_notifications_use_total_changed_template(self):
        calls = self.notifier.notify.call_args_list
        templates = [c.args[1] for c in calls]
        assert all(t == "total_changed" for t in templates)

    def and_old_total_is_passed_in_kwargs(self):
        calls = self.notifier.notify.call_args_list
        old_totals = [c.kwargs["old_total"] for c in calls]
        assert all(t == 2 for t in old_totals)
