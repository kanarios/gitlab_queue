"""Test capture_queue_positions returns empty dict for empty queue."""

import vedro

from .._helpers import (
    create_mock_queue_manager,
    create_position_notifier,
)


class Scenario(vedro.Scenario):
    subject = "capture_queue_positions returns empty dict for empty queue"

    async def given_empty_queue(self):
        self.queue_manager = create_mock_queue_manager(queue_items=[])
        self.position_notifier = create_position_notifier(
            queue_manager=self.queue_manager,
        )

    async def when_capture_queue_positions_is_called(self):
        self.positions = await self.position_notifier.capture_queue_positions()

    def then_result_is_empty_dict(self):
        assert self.positions == {}
