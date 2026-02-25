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
        """
        Trigger the manager to broadcast a "queue:updated" event using prepared test data.
        
        Prepares self.queue_data as a single-item list (mr_iid=42, title="Test", status=QueueState.REBASING) and self.stats_data mapping QueueState.QUEUED to 0 and QueueState.REBASING to 1, then calls manager.broadcast_queue_updated with those values.
        """
        self.queue_data = [{"mr_iid": 42, "title": "Test", "status": QueueState.REBASING}]
        self.stats_data = {QueueState.QUEUED: 0, QueueState.REBASING: 1}
        await self.manager.broadcast_queue_updated(self.queue_data, self.stats_data)

    def then_broadcast_should_be_sent_to_connection(self):
        """
        Assert that a "queue:updated" broadcast was sent to the mock WebSocket with the expected payload.
        
        Verifies that send_json was awaited exactly once and that the sent message has:
        - "type" equal to "queue:updated"
        - "data.queue" equal to self.queue_data
        - "data.stats" equal to self.stats_data
        """
        self.mock_ws.send_json.assert_awaited_once()
        call_args = self.mock_ws.send_json.call_args[0][0]
        assert call_args["type"] == "queue:updated"
        assert call_args["data"]["queue"] == self.queue_data
        assert call_args["data"]["stats"] == self.stats_data
