"""Test that WebSocketManager broadcasts mr:completed events."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import vedro
from scenarios.library import QueueState

from gitlab_queue.api.websocket import WebSocketManager


class Scenario(vedro.Scenario):
    subject = "WebSocketManager broadcasts mr:completed events to connected clients"

    def given_mock_websocket_connection(self):
        # Create a mock WebSocket to test broadcast functionality
        self.manager = WebSocketManager()
        self.mock_ws = MagicMock()
        self.mock_ws.send_json = AsyncMock()
        self.mock_ws.client_state = MagicMock()
        self.mock_ws.client_state.name = "CONNECTED"
        self.manager._connections.add(self.mock_ws)
        self.finished_at = datetime.now(UTC)

    async def when_mr_completed_is_broadcast(self):
        await self.manager.broadcast_mr_completed(
            mr_iid=42,
            status=QueueState.MERGED,
            finished_at=self.finished_at,
        )

    def then_broadcast_should_contain_completion_info(self):
        self.mock_ws.send_json.assert_called_once()
        call_args = self.mock_ws.send_json.call_args[0][0]
        assert call_args["type"] == "mr:completed"
        assert call_args["data"]["iid"] == 42
        assert call_args["data"]["status"] == "merged"
        assert call_args["data"]["finishedAt"] is not None
