"""Test that WebSocketManager broadcasts mr:status_changed events."""

from __future__ import annotations

import vedro
from scenarios.fakes import FakeWebSocket
from scenarios.library import QueueState

from gitlab_queue.api.websocket import WebSocketManager


class Scenario(vedro.Scenario):
    subject = "WebSocketManager broadcasts mr:status_changed events to connected clients"

    def given_fake_websocket_connection(self):
        self.manager = WebSocketManager()
        self.fake_ws = FakeWebSocket()
        self.manager._connections.add(self.fake_ws)

    async def when_mr_status_changed_is_broadcast(self):
        await self.manager.broadcast_mr_status_changed(42, QueueState.QUEUED, QueueState.REBASING)

    def then_broadcast_should_contain_status_change(self):
        assert self.fake_ws.send_count == 1
        message = self.fake_ws.last_sent
        assert message["type"] == "mr:status_changed"
        assert message["data"]["iid"] == 42
        assert message["data"]["oldStatus"] == "queued"
        assert message["data"]["newStatus"] == "rebasing"
