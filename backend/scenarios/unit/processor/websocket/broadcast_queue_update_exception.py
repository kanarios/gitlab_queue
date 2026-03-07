"""Test _broadcast_queue_update handles exception from broadcast_queue_updated gracefully.

Lines 1516-1517: when broadcast_queue_updated raises an Exception,
catch it and log warning without propagating.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import structlog.testing
import vedro

from .._helpers import create_mock_processor


@dataclass
class FailingWebSocketManager:
    """WebSocket manager that raises on broadcast_queue_updated."""

    broadcast_attempted: bool = False

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
        # Should not raise — exception is caught and logged as warning
        self.exception = None
        with structlog.testing.capture_logs() as self.captured:
            try:
                await self.processor._broadcast_queue_update()
            except Exception as e:
                self.exception = e

    def then_no_exception_was_raised(self):
        assert self.exception is None

    def and_broadcast_was_attempted(self):
        assert self.websocket_manager.broadcast_attempted is True

    def and_warning_about_broadcast_failure_was_logged(self):
        warning_entries = [e for e in self.captured if e.get("log_level") == "warning"]
        broadcast_warnings = [e for e in warning_entries if "Failed to broadcast queue update" in e.get("event", "")]
        assert len(broadcast_warnings) == 1
