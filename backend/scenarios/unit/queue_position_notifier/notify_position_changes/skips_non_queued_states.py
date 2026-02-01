"""Test _notify_position_changes skips non-queued states."""

import vedro
from vedro import params

from .._helpers import (
    MockQueueItem,
    create_mock_notifier,
    create_mock_queue_manager,
    create_position_notifier,
)


class Scenario(vedro.Scenario):
    subject = "_notify_position_changes skips MR in {state} state"

    @params("rebasing")
    @params("testing")
    @params("merging")
    def __init__(self, state: str):
        self.non_queued_state = state

    def given_mr_in_non_queued_state_with_changed_position(self):
        # Before: MR 101 at position 1, MR 102 at position 3
        # After: MR 101 is non-queued (skipped), MR 102 is queued at position 2
        # MR 102 moves from 3 to 2, so it should be notified
        self.positions_before = {101: 1, 102: 3}
        queue_items_after = [
            MockQueueItem(mr_iid=101, state=self.non_queued_state),
            MockQueueItem(mr_iid=102, state="queued"),
        ]
        self.notifier = create_mock_notifier()
        self.queue_manager = create_mock_queue_manager(queue_items_after)
        self.position_notifier = create_position_notifier(
            notifier=self.notifier,
            queue_manager=self.queue_manager,
        )

    async def when_notify_position_changes_is_called(self):
        self.notified_count = await self.position_notifier._notify_position_changes(
            excluded_mr_iid=999,
            positions_before=self.positions_before,
            log_context="",
        )

    def then_mr_in_non_queued_state_is_not_notified(self):
        calls = self.notifier.notify.call_args_list
        notified_iids = [call.kwargs.get("mr_iid", call.args[0]) for call in calls]
        assert 101 not in notified_iids

    def and_queued_mr_is_notified(self):
        calls = self.notifier.notify.call_args_list
        notified_iids = [call.kwargs.get("mr_iid", call.args[0]) for call in calls]
        assert 102 in notified_iids
