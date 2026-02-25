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
        """
        Invoke the position notifier using the scenario's prepared inputs and record the returned notified count.
        
        The call uses excluded_mr_iid=999, positions_before and old_total derived from the scenario, and an empty log_context; the result is stored on self.notified_count.
        
        Returns:
            notified_count (int): Number of merge requests that were notified.
        """
        self.notified_count = await self.position_notifier._notify_position_changes(
            excluded_mr_iid=999,
            positions_before=self.positions_before,
            old_total=len(self.positions_before),
            log_context="",
        )

    @property
    def notified_iids(self) -> list[int]:
        """
        Collect the merge request IIDs that were passed to the notifier's recorded calls.
        
        Extracts the `mr_iid` value from each recorded call to `self.notifier.notify` (preferring the `mr_iid` keyword argument, falling back to the first positional argument) and returns them in call order.
        
        Returns:
            list[int]: List of MR IIDs that were passed to the notifier.
        """
        return [call.kwargs.get("mr_iid", call.args[0]) for call in self.notifier.notify.call_args_list]

    def then_mr_in_non_queued_state_is_not_notified(self):
        """
        Asserts that merge request with IID 101 was not notified.
        
        Raises an AssertionError if IID 101 appears in the recorded notified IIDs.
        """
        assert 101 not in self.notified_iids

    def and_queued_mr_is_notified(self):
        assert 102 in self.notified_iids
