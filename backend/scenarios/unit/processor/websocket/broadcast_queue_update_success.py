"""Test _broadcast_queue_update sends queue data through websocket manager.

Lines 1482-1517: when _websocket_manager is set, fetch queue items and stats,
build queue_data list, and call broadcast_queue_updated.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import vedro

from .._helpers import (
    create_mock_processor,
    create_test_queue_item,
)


class Scenario(vedro.Scenario):
    subject = "broadcast_queue_update sends queue data to websocket clients"

    def given_processor_with_websocket_manager_and_queue_items(self):
        self.processor = create_mock_processor()

        # Set up queue items
        self.item1 = create_test_queue_item(mr_iid=10, state="testing")
        self.item1.author_avatar = None
        self.item1.started_at = None

        self.item2 = create_test_queue_item(mr_iid=20, state="queued")
        self.item2.author_avatar = None
        self.item2.started_at = datetime.now(UTC)

        self.processor.queue_manager.get_active_queue = AsyncMock(return_value=[self.item1, self.item2])
        self.stats = {"total": 2, "merged_today": 0}
        self.processor.queue_manager.get_queue_stats = AsyncMock(return_value=self.stats)

        # Set up websocket manager
        self.websocket_manager = MagicMock()
        self.websocket_manager.broadcast_queue_updated = AsyncMock()
        self.processor.set_websocket_manager(self.websocket_manager)

    async def when_broadcast_queue_update_is_called(self):
        await self.processor._broadcast_queue_update()

    def then_broadcast_queue_updated_was_called(self):
        self.websocket_manager.broadcast_queue_updated.assert_awaited_once()

    def and_queue_data_has_correct_count(self):
        call_args = self.websocket_manager.broadcast_queue_updated.call_args
        queue_data = call_args[0][0]
        assert len(queue_data) == 2

    def and_first_item_has_correct_position(self):
        call_args = self.websocket_manager.broadcast_queue_updated.call_args
        queue_data = call_args[0][0]
        assert queue_data[0]["position"] == 1
        assert queue_data[1]["position"] == 2

    def and_queue_stats_are_passed(self):
        call_args = self.websocket_manager.broadcast_queue_updated.call_args
        stats = call_args[0][1]
        assert stats == self.stats
