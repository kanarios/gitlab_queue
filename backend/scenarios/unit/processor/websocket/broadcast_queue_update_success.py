"""Test _broadcast_queue_update sends queue data through websocket manager.

Lines 1482-1517: when _websocket_manager is set, fetch queue items and stats,
build queue_data list, and call broadcast_queue_updated.
"""

from __future__ import annotations

from datetime import UTC, datetime

import vedro

from scenarios.fakes import FakeWebSocketManager

from .._helpers import (
    create_mock_processor,
    create_test_queue_item,
)


class Scenario(vedro.Scenario):
    subject = "broadcast_queue_update sends queue data to websocket clients"

    def given_processor_with_websocket_manager_and_queue_items(self):
        self.item1 = create_test_queue_item(mr_iid=10, state="testing")
        self.item1.author_avatar = None
        self.item1.started_at = None

        self.item2 = create_test_queue_item(mr_iid=20, state="queued")
        self.item2.author_avatar = None
        self.item2.started_at = datetime.now(UTC)

        self.processor = create_mock_processor()
        self.processor.queue_manager.add_item(self.item1)
        self.processor.queue_manager.add_item(self.item2)
        self.stats = {"total": 2, "merged_today": 0}
        self.processor.queue_manager.queue_stats = self.stats

        # Set up websocket manager
        self.websocket_manager = FakeWebSocketManager()
        self.processor.set_websocket_manager(self.websocket_manager)

    async def when_broadcast_queue_update_is_called(self):
        await self.processor._broadcast_queue_update()

    def then_broadcast_queue_updated_was_called(self):
        assert len(self.websocket_manager.broadcast_calls) == 1

    def and_queue_data_has_correct_count(self):
        call = self.websocket_manager.broadcast_calls[0]
        queue_data = call["queue"]
        assert len(queue_data) == 2

    def and_first_item_has_correct_position(self):
        call = self.websocket_manager.broadcast_calls[0]
        queue_data = call["queue"]
        assert queue_data[0]["position"] == 1
        assert queue_data[1]["position"] == 2

    def and_queue_stats_are_passed(self):
        call = self.websocket_manager.broadcast_calls[0]
        stats = call["stats"]
        assert stats == self.stats
