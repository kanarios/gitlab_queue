"""Test that WebSocketManager broadcasts mr:status_changed events."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import vedro
from scenarios.library import QueueState

from gitlab_queue.api.websocket import WebSocketManager


class Scenario(vedro.Scenario):
    subject = "WebSocketManager broadcasts mr:status_changed events to connected clients"

    def given_mock_websocket_connection(self):
        # Create a mock WebSocket to test broadcast functionality
        self.manager = WebSocketManager()
        self.mock_ws = MagicMock()
        self.mock_ws.send_json = AsyncMock()
        self.mock_ws.client_state = MagicMock()
        self.mock_ws.client_state.name = "CONNECTED"
        self.manager._connections.add(self.mock_ws)

    async def when_mr_status_changed_is_broadcast(self):
        """
        Trigger broadcasting an mr:status_changed event for IID 42 with a queued→rebasing status transition.

        This awaits the WebSocketManager to broadcast an event indicating merge request 42 changed from QueueState.QUEUED to QueueState.REBASING.
        """
        await self.manager.broadcast_mr_status_changed(42, QueueState.QUEUED, QueueState.REBASING)

    def then_broadcast_should_contain_status_change(self):
        """
        Assert that the mocked WebSocket received an mr:status_changed broadcast with the expected payload.

        Verifies that send_json was awaited exactly once and that the sent JSON has:
        - type "mr:status_changed"
        - data.iid equals 42
        - data.oldStatus equals "queued"
        - data.newStatus equals "rebasing"
        """
        self.mock_ws.send_json.assert_awaited_once()
        call_args = self.mock_ws.send_json.call_args[0][0]
        assert call_args["type"] == "mr:status_changed"
        assert call_args["data"]["iid"] == 42
        assert call_args["data"]["oldStatus"] == "queued"
        assert call_args["data"]["newStatus"] == "rebasing"
