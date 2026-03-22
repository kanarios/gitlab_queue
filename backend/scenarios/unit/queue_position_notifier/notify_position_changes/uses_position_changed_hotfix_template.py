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
        """
        Set up a scenario with two merge requests whose positions shift because of a preceding hotfix.

        Initializes:
        - positions_before mapping MR 101 -> 1 and MR 102 -> 2 and old_total = 2.
        - queue_items_after containing a hotfix MR 100 followed by queued MRs 101 and 102.
        - a mock notifier, a mock queue manager configured with queue_items_after, and a position_notifier using those mocks.
        """
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
        """
        Calls the position notifier to notify merge requests whose positions changed due to a hotfix and records how many notifications were sent.

        Returns:
            notified_count (int): The number of notifications that were sent and stored on self.notified_count.
        """
        self.notified_count = await self.position_notifier._notify_position_changes(
            99999,
            excluded_mr_iid=100,
            positions_before=self.positions_before,
            old_total=self.old_total,
            log_context=" due to hotfix",
            is_hotfix=True,
        )

    def then_two_notifications_are_sent(self):
        """
        Assert that the notifier's notify method was called exactly two times.
        """
        assert self.notifier.notify.call_count == 2

    def and_notified_count_is_2(self):
        """
        Asserts that exactly two notifications were reported by the notifier.

        Raises an AssertionError if the recorded notified count is not equal to 2.
        """
        assert self.notified_count == 2

    def and_all_notifications_use_position_changed_hotfix_template(self):
        """
        Asserts that every sent notification used the "position_changed_hotfix" template.

        Raises:
            AssertionError: If any notification was sent with a different template.
        """
        calls = self.notifier.notify.call_args_list
        templates = [c.args[1] for c in calls]
        assert all(t == "position_changed_hotfix" for t in templates)

    def and_positions_shifted_down_by_one(self):
        """
        Asserts that notifications indicate the affected merge requests' positions each shifted down by one.

        Verifies the notifier call arguments contain notifications for MR 101 changing from position 1 to 2 and MR 102 changing from position 2 to 3; raises an assertion error if the actual notifications do not match these expected values.
        """
        calls = self.notifier.notify.call_args_list
        notifications = [(c.args[0], c.kwargs["position"], c.kwargs["old_position"]) for c in calls]
        expected = {(101, 2, 1), (102, 3, 2)}
        assert set(notifications) == expected
