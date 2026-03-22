"""Test notify_affected_mrs_after_mr_added notifies with hotfix context."""

import vedro

from .._helpers import (
    MockQueueItem,
    create_mock_notifier,
    create_mock_queue_manager,
    create_position_notifier,
)


class Scenario(vedro.Scenario):
    subject = "notify_affected_mrs_after_mr_added notifies affected MRs when hotfix added"

    async def given_positions_before_hotfix_added(self):
        """
        Set up test context with two existing MRs and a newly added hotfix MR.

        Creates:
        - self.hotfix_mr_iid: IID of the added hotfix MR (100).
        - self.positions_before: mapping of existing MR IIDs to their positions.
        - self.old_total: number of MRs before the hotfix was added.
        - self.notifier: mock notifier instance.
        - self.queue_manager: mock queue manager initialized with queued items including the hotfix.
        - self.position_notifier: position notifier configured with the mock notifier and queue manager.

        The queue after addition contains the hotfix MR (marked `is_hotfix=True`) followed by the existing MRs.
        """
        self.hotfix_mr_iid = 100
        self.positions_before = {101: 1, 102: 2}
        self.old_total = len(self.positions_before)
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
        """
        Trigger notification of affected merge requests after a hotfix MR is added.

        Calls the position notifier with the hotfix MR IID, the positions before the addition, the previous total, and indicates a hotfix context.
        """
        await self.position_notifier.notify_affected_mrs_after_mr_added(
            99999,
            added_mr_iid=self.hotfix_mr_iid,
            positions_before=self.positions_before,
            old_total=self.old_total,
            is_hotfix=True,
        )

    def then_affected_mrs_are_notified(self):
        """
        Assert that notifier.notify was called exactly two times.

        Raises:
            AssertionError: if notifier.notify was called a number of times other than two.
        """
        assert self.notifier.notify.call_count == 2

    def and_hotfix_mr_is_not_notified(self):
        calls = self.notifier.notify.call_args_list
        # mr_iid is always positional (args[0])
        notified_iids = [call.args[0] for call in calls]
        assert self.hotfix_mr_iid not in notified_iids

    def and_positions_shifted_down_by_one(self):
        """
        Asserts that notified merge requests had their positions shifted down by one after a hotfix was added.

        Checks that notifier.notify was called with tuples of (mr_iid, position, old_position) matching the expected set {(101, 2, 1), (102, 3, 2)}.
        """
        calls = self.notifier.notify.call_args_list
        # mr_iid is positional (args[0])
        # position and old_position are keyword-only
        notifications = [(c.args[0], c.kwargs["position"], c.kwargs["old_position"]) for c in calls]
        expected = {(101, 2, 1), (102, 3, 2)}
        assert set(notifications) == expected

    def and_notifications_use_position_changed_hotfix_template(self):
        """
        Asserts that every notification sent used the "position_changed_hotfix" template.

        Raises an AssertionError if any recorded notify call used a different template.
        """
        calls = self.notifier.notify.call_args_list
        templates = [c.args[1] for c in calls]
        assert all(t == "position_changed_hotfix" for t in templates)
