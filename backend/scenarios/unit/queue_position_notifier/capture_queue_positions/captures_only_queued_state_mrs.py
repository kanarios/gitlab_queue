"""Test capture_queue_positions captures only queued state MRs."""

import vedro

from .._helpers import (
    create_mock_queue_manager,
    create_position_notifier,
    create_queue_with_mixed_states,
)


class Scenario(vedro.Scenario):
    subject = "capture_queue_positions captures only MRs in queued state"

    async def given_queue_with_mixed_states(self):
        queue_items = create_queue_with_mixed_states()
        self.queue_manager = create_mock_queue_manager(queue_items)
        self.position_notifier = create_position_notifier(
            queue_manager=self.queue_manager,
        )

    async def when_capture_queue_positions_is_called(self):
        self.positions = await self.position_notifier.capture_queue_positions()

    def then_only_queued_mrs_are_captured(self):
        assert 101 in self.positions
        assert 103 in self.positions
        assert 105 in self.positions

    def and_non_queued_mrs_are_not_captured(self):
        assert 102 not in self.positions
        assert 104 not in self.positions

    def and_captured_count_is_3(self):
        assert len(self.positions) == 3
