"""Test _notify_position_changes uses total_changed template when only total changes."""

import vedro

from .._helpers import (
    MockQueueItem,
    create_mock_notifier,
    create_mock_queue_manager,
    create_position_notifier,
)


class Scenario(vedro.Scenario):
    subject = "_notify_position_changes uses total_changed template when only total changes"

    def given_mr_with_same_position_but_different_total(self):
        """
        Set up a scenario where merge request 101 retains its position but the queue total changes.
        
        Initializes:
        - positions_before mapping MR 101 to position 1
        - old_total set to 1
        - queue_items_after containing two queued MRs (101 and 102)
        Then constructs a mock notifier, a mock queue manager seeded with queue_items_after, and a position_notifier using those mocks.
        """
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

    async def when_notify_position_changes_is_called(self):
        """
        Invoke the position notifier to detect and record position change notifications.
        
        Calls self.position_notifier._notify_position_changes with the test's configured
        excluded_mr_iid, positions_before, old_total, log_context, and is_hotfix values and
        stores the resulting notified count on self.notified_count.
        """
        self.notified_count = await self.position_notifier._notify_position_changes(
            excluded_mr_iid=999,
            positions_before=self.positions_before,
            old_total=self.old_total,
            log_context="",
            is_hotfix=False,
        )

    def then_one_notification_is_sent(self):
        """
        Asserts that the notifier's `notify` method was called exactly once.
        """
        assert self.notifier.notify.call_count == 1

    def and_notified_count_is_1(self):
        """
        Asserts that exactly one notification was recorded.
        
        Raises:
        	AssertionError: If the recorded notified_count is not 1.
        """
        assert self.notified_count == 1

    def and_mr_102_is_not_notified(self):
        """
        Asserts that MR with IID 102 was not passed to the notifier.
        
        Checks the notifier's recorded notify calls and raises an AssertionError if 102 appears among the notified MR IIDs.
        """
        calls = self.notifier.notify.call_args_list
        notified_iids = [c.args[0] for c in calls]
        assert 102 not in notified_iids

    def and_notification_uses_total_changed_template(self):
        """
        Asserts that the first notification used the "total_changed" template.
        
        Verifies the notifier's first call passed "total_changed" as the template argument.
        """
        call = self.notifier.notify.call_args_list[0]
        template = call.args[1]
        assert template == "total_changed"

    def and_old_total_is_passed_in_kwargs(self):
        """
        Asserts that the notifier call includes the original total under the 'old_total' keyword.
        
        Checks the first recorded notify call's kwargs and verifies that 'old_total' equals 1.
        """
        call = self.notifier.notify.call_args_list[0]
        assert call.kwargs["old_total"] == 1
