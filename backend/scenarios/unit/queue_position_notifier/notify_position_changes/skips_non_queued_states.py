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

    async def given_mr_in_non_queued_state_with_changed_position(self):
        self.positions_before = {101: 1, 102: 2}
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
        notified_iids = [call[0][0] for call in calls]
        assert 101 not in notified_iids
