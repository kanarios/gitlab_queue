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
        """
        Set up test state for a scenario where a regular merge request is added and existing MRs should be notified.

        Initializes:
        - added_mr_iid: IID of the newly added MR (103).
        - positions_before: mapping of existing MR IIDs to their positions before addition ({101: 1, 102: 2}).
        - old_total: previous total number of MRs (2).
        - queue_manager with queue items for MRs 101, 102, 103 all in "queued" state.
        - notifier: a mock notifier instance.
        - position_notifier: a notifier wired to the mock notifier and queue manager.
        """
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
        """
        Invoke the position notifier to notify affected merge requests after a regular merge request is added.

        Calls notify_affected_mrs_after_mr_added using the scenario's added_mr_iid, positions_before, and old_total, with is_hotfix set to False.
        """
        await self.position_notifier.notify_affected_mrs_after_mr_added(
            added_mr_iid=self.added_mr_iid,
            positions_before=self.positions_before,
            old_total=self.old_total,
            is_hotfix=False,
        )

    def then_existing_mrs_are_notified(self):
        """
        Asserts that exactly two existing merge requests were notified.

        Raises:
                AssertionError: If the notifier was called a number of times other than 2.
        """
        assert self.notifier.notify.call_count == 2

    def and_added_mr_is_not_notified(self):
        """
        Verify that the newly added merge request is not among the notified merge requests.

        This test inspects the notifier's recorded calls and asserts that `self.added_mr_iid` was not targeted for notification.
        """
        calls = self.notifier.notify.call_args_list
        notified_iids = [c.args[0] for c in calls]
        assert self.added_mr_iid not in notified_iids

    def and_notifications_use_total_changed_template(self):
        """
        Asserts that every notification used the "total_changed" template.

        Raises:
            AssertionError: If any notification was sent with a template other than "total_changed".
        """
        calls = self.notifier.notify.call_args_list
        templates = [c.args[1] for c in calls]
        assert all(t == "total_changed" for t in templates)

    def and_old_total_is_passed_in_kwargs(self):
        """
        Verify that every notification call received the original total (old_total = 2) in its keyword arguments.

        Raises:
            AssertionError: If any notification's `old_total` is not equal to 2.
        """
        calls = self.notifier.notify.call_args_list
        old_totals = [c.kwargs["old_total"] for c in calls]
        assert all(t == self.old_total for t in old_totals)
