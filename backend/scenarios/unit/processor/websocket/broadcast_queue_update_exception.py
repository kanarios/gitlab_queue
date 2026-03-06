"""Test _broadcast_queue_update handles exception from broadcast_queue_updated gracefully.

Lines 1516-1517: when broadcast_queue_updated raises an Exception,
catch it and log warning without propagating.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import vedro

from .._helpers import create_mock_processor


@dataclass
class FailingWebSocketManager:
    """WebSocket manager that raises on broadcast_queue_updated."""

    broadcast_attempted: bool = False
    broadcast_calls: list[dict[str, Any]] = field(default_factory=list)

    async def broadcast_queue_updated(self, queue: list[dict[str, Any]], stats: dict[str, Any]) -> None:
        self.broadcast_attempted = True
        raise Exception("WebSocket connection lost")


class Scenario(vedro.Scenario):
    subject = "broadcast_queue_update handles exception from websocket manager gracefully"

    def given_processor_with_websocket_manager_that_raises(self):
        self.processor = create_mock_processor()

        # WebSocket manager whose broadcast raises an exception
        self.websocket_manager = FailingWebSocketManager()
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
        assert self.websocket_manager.broadcast_attempted is True
