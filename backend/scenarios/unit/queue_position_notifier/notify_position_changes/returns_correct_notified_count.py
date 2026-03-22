"""Test _notify_position_changes returns correct notified count.

NOTE: Intentionally testing private method _notify_position_changes
to verify internal logic (return count behavior).
Public methods notify_affected_mrs_after_completion and
notify_affected_mrs_after_mr_added don't expose the count.
"""

import vedro
from vedro import params

from .._helpers import (
    MockQueueItem,
    create_mock_notifier,
    create_mock_queue_manager,
    create_position_notifier,
)


class Scenario(vedro.Scenario):
    subject = "notify_position_changes returns notified count {expected_count}"

    @params(
        {101: 2, 102: 3, 103: 4},
        [
            MockQueueItem(mr_iid=101, state="queued"),
            MockQueueItem(mr_iid=102, state="queued"),
            MockQueueItem(mr_iid=103, state="queued"),
        ],
        3,
    )
    @params(
        {101: 1, 102: 2},
        [
            MockQueueItem(mr_iid=101, state="queued"),
            MockQueueItem(mr_iid=102, state="queued"),
        ],
        0,
    )
    @params(
        {101: 2},
        [
            MockQueueItem(mr_iid=101, state="queued"),
            MockQueueItem(mr_iid=102, state="queued"),
        ],
        1,
    )
    def __init__(
        self,
        positions_before: dict,
        queue_items_after: list,
        expected_count: int,
    ):
        self.positions_before = positions_before
        self.queue_items_after = queue_items_after
        self.expected_count = expected_count

    async def given_queue_configuration(self):
        self.notifier = create_mock_notifier()
        self.queue_manager = create_mock_queue_manager(self.queue_items_after)
        self.position_notifier = create_position_notifier(
            notifier=self.notifier,
            queue_manager=self.queue_manager,
        )

    async def when_notify_position_changes_is_called(self):
        """
        Invoke the position notifier to compute how many merge requests were notified and store the result.

        This awaits a call to the notifier's internal `_notify_position_changes` with the current
        test inputs and assigns the returned notified count to `self.notified_count`.
        """
        self.notified_count = await self.position_notifier._notify_position_changes(
            99999,
            excluded_mr_iid=999,
            positions_before=self.positions_before,
            old_total=len(self.positions_before),
            log_context="",
        )

    def then_notified_count_matches_expected(self):
        assert self.notified_count == self.expected_count
