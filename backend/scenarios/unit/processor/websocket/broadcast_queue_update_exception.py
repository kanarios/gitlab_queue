"""Test _broadcast_queue_update handles exception from broadcast_queue_updated gracefully.

Lines 1516-1517: when broadcast_queue_updated raises an Exception,
catch it and log warning without propagating.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import vedro

from .._helpers import create_mock_processor


class Scenario(vedro.Scenario):
    subject = "broadcast_queue_update handles exception from websocket manager gracefully"

    def given_processor_with_websocket_manager_that_raises(self):
        self.processor = create_mock_processor()

        # Queue manager returns items for broadcast
        self.processor.queue_manager.get_active_queue = AsyncMock(return_value=[])
        self.processor.queue_manager.get_queue_stats = AsyncMock(return_value={"total": 0})

        # WebSocket manager whose broadcast raises an exception
        self.websocket_manager = MagicMock()
        self.websocket_manager.broadcast_queue_updated = AsyncMock(side_effect=Exception("WebSocket connection lost"))
        self.processor.set_websocket_manager(self.websocket_manager)

    async def when_broadcast_queue_update_is_called(self):
        # Should not raise — exception is caught at lines 1516-1517
        self.exception = None
        try:
            await self.processor._broadcast_queue_update()
        except Exception as e:
            self.exception = e

    def then_no_exception_was_raised(self):
        assert self.exception is None

    def and_broadcast_was_attempted(self):
        self.websocket_manager.broadcast_queue_updated.assert_awaited_once()
