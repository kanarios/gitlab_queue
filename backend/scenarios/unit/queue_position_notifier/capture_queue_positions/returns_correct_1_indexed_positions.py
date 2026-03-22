"""Test capture_queue_positions returns correct 1-indexed positions."""

import vedro

from .._helpers import (
    create_mock_queue_manager,
    create_position_notifier,
    create_queue_all_queued,
)


class Scenario(vedro.Scenario):
    subject = "capture_queue_positions returns correct 1-indexed positions"

    async def given_queue_with_three_queued_mrs(self):
        self.queue_items = create_queue_all_queued(3)
        self.mr_iids = [item.mr_iid for item in self.queue_items]
        self.queue_manager = create_mock_queue_manager(self.queue_items)
        self.position_notifier = create_position_notifier(
            queue_manager=self.queue_manager,
        )

    async def when_capture_queue_positions_is_called(self):
        self.positions = await self.position_notifier.capture_queue_positions(99999)

    def then_first_mr_has_position_1(self):
        assert self.positions[self.mr_iids[0]] == 1

    def and_second_mr_has_position_2(self):
        assert self.positions[self.mr_iids[1]] == 2

    def and_third_mr_has_position_3(self):
        assert self.positions[self.mr_iids[2]] == 3
