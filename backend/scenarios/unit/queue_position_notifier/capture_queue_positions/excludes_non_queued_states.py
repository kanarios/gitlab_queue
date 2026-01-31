"""Test capture_queue_positions excludes non-queued states."""

import vedro
from vedro import params

from .._helpers import (
    MockQueueItem,
    create_mock_queue_manager,
    create_position_notifier,
)


class Scenario(vedro.Scenario):
    subject = "capture_queue_positions excludes MR in {state} state"

    @params("rebasing")
    @params("testing")
    @params("merging")
    def __init__(self, state: str):
        self.excluded_state = state

    async def given_queue_with_mr_in_excluded_state(self):
        queue_items = [
            MockQueueItem(mr_iid=101, state="queued"),
            MockQueueItem(mr_iid=102, state=self.excluded_state),
        ]
        self.queue_manager = create_mock_queue_manager(queue_items)
        self.position_notifier = create_position_notifier(
            queue_manager=self.queue_manager,
        )

    async def when_capture_queue_positions_is_called(self):
        self.positions = await self.position_notifier.capture_queue_positions()

    def then_mr_in_excluded_state_is_not_captured(self):
        assert 102 not in self.positions

    def and_queued_mr_is_captured(self):
        assert 101 in self.positions
