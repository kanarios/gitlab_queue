"""Test that WebSocketManager removes failed connections during broadcast."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import vedro
from scenarios.contexts.api_helpers import created_test_app


class Scenario(vedro.Scenario):
    subject = "WebSocketManager removes disconnected clients during broadcast"

    def given_websocket_manager_with_mock_connection(self):
        self.app, self.state = created_test_app()
        self.manager = self.state.websocket_manager

        # Create a mock WebSocket that will fail on send
        self.mock_ws = MagicMock()
        self.mock_ws.send_json = AsyncMock(side_effect=Exception("Connection closed"))

        # Add directly to manager
        self.manager._connections.add(self.mock_ws)
        self.count_before = self.manager.connection_count

    async def when_broadcast_is_attempted(self):
        await self.manager.broadcast({"type": "test", "data": {}})
        self.count_after = self.manager.connection_count

    def then_failed_connection_should_be_removed(self):
        assert self.count_before == 1
        assert self.count_after == 0
