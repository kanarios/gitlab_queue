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
        queue_items = create_queue_all_queued(3)
        self.queue_manager = create_mock_queue_manager(queue_items)
        self.position_notifier = create_position_notifier(
            queue_manager=self.queue_manager,
        )

    async def when_capture_queue_positions_is_called(self):
        self.positions = await self.position_notifier.capture_queue_positions()

    def then_first_mr_has_position_1(self):
        assert self.positions[101] == 1

    def and_second_mr_has_position_2(self):
        assert self.positions[102] == 2

    def and_third_mr_has_position_3(self):
        assert self.positions[103] == 3
