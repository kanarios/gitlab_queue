"""Test _broadcast_queue_update returns immediately when no WebSocket manager.

Line 1482 (early return): when _websocket_manager is None, return without any calls.
"""

from __future__ import annotations

import vedro

from .._helpers import create_mock_processor


class Scenario(vedro.Scenario):
    subject = "broadcast_queue_update returns early when no websocket manager"

    def given_processor_without_websocket_manager(self):
        self.processor = create_mock_processor()
        # _websocket_manager is None by default

    async def when_broadcast_queue_update_is_called(self):
        await self.processor._broadcast_queue_update()

    def then_no_queue_calls_were_made(self):
        assert len(self.processor.queue_manager.get_queue_item_calls) == 0

    def and_websocket_manager_is_still_none(self):
        assert self.processor._websocket_manager is None
