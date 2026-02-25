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
        """
        Set up test state: one MR keeps the same position while the total changes and a hotfix will be applied.
        
        Creates positions_before = {101: 1}, old_total = 1, a post-change queue containing MR 101 and 102 (both queued), a mock notifier, a mock queue manager seeded with the queue, and a position_notifier wired to those mocks.
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

    async def when_notify_position_changes_is_called_with_hotfix(self):
        """
        Call _notify_position_changes with the hotfix flag and store the resulting notified count on the scenario.
        
        This step invokes the position_notifier's _notify_position_changes with excluded_mr_iid=102, the scenario's positions_before and old_total, log_context set to " due to hotfix", and is_hotfix=True. The numeric result is stored in self.notified_count.
        """
        self.notified_count = await self.position_notifier._notify_position_changes(
            excluded_mr_iid=102,
            positions_before=self.positions_before,
            old_total=self.old_total,
            log_context=" due to hotfix",
            is_hotfix=True,
        )

    def then_one_notification_is_sent(self):
        """
        Assert that exactly one notification was sent by the notifier.
        
        Raises an AssertionError if the notifier's `notify` method was called a number of times other than one.
        """
        assert self.notifier.notify.call_count == 1

    def and_notified_count_is_1(self):
        """
        Asserts that exactly one notification was recorded.
        
        Raises an AssertionError if the recorded notified count is not equal to 1.
        """
        assert self.notified_count == 1

    def and_notification_uses_total_changed_hotfix_template(self):
        """
        Asserts that the notifier was called with the "total_changed_hotfix" template.
        
        Checks the first call to the notifier and verifies its template argument equals "total_changed_hotfix".
        """
        call = self.notifier.notify.call_args_list[0]
        template = call.args[1]
        assert template == "total_changed_hotfix"

    def and_old_total_is_passed_in_kwargs(self):
        """
        Asserts that the first call to the notifier included `old_total` with value 1 in its keyword arguments.
        
        Checks the recorded call arguments on `self.notifier.notify` and raises an AssertionError if `old_total` in the call's kwargs is not equal to 1.
        """
        call = self.notifier.notify.call_args_list[0]
        assert call.kwargs["old_total"] == 1
