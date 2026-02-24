"""Test that WebSocketManager broadcasts queue:updated events."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import vedro
from scenarios.library import QueueState

from gitlab_queue.api.websocket import WebSocketManager


class Scenario(vedro.Scenario):
    subject = "WebSocketManager broadcasts queue:updated events to connected clients"

    def given_mock_websocket_connection(self):
        # Create a mock WebSocket to test broadcast functionality
        self.manager = WebSocketManager()
        self.mock_ws = MagicMock()
        self.mock_ws.send_json = AsyncMock()
        self.mock_ws.client_state = MagicMock()
        # Simulate connected state
        self.mock_ws.client_state.name = "CONNECTED"
        self.manager._connections.add(self.mock_ws)

    async def when_queue_updated_is_broadcast(self):
        self.queue_data = [{"mr_iid": 42, "title": "Test", "status": QueueState.REBASING}]
        self.stats_data = {QueueState.QUEUED: 0, QueueState.REBASING: 1}
        await self.manager.broadcast_queue_updated(self.queue_data, self.stats_data)

    def then_broadcast_should_be_sent_to_connection(self):
        self.mock_ws.send_json.assert_awaited_once()
        call_args = self.mock_ws.send_json.call_args[0][0]
        assert call_args["type"] == "queue:updated"
        assert call_args["data"]["queue"] == self.queue_data
        assert call_args["data"]["stats"] == self.stats_data
