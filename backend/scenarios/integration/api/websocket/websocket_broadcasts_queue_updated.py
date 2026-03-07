"""Test that WebSocketManager broadcasts queue:updated events."""

from __future__ import annotations

import vedro
from scenarios.fakes import FakeWebSocket
from scenarios.library import QueueState

from gitlab_queue.api.websocket import WebSocketManager


class Scenario(vedro.Scenario):
    subject = "WebSocketManager broadcasts queue:updated events to connected clients"

    def given_fake_websocket_connection(self):
        self.manager = WebSocketManager()
        self.fake_ws = FakeWebSocket()
        self.manager._connections.add(self.fake_ws)

    async def when_queue_updated_is_broadcast(self):
        self.queue_data = [{"mr_iid": 42, "title": "Test", "status": QueueState.REBASING}]
        self.stats_data = {QueueState.QUEUED: 0, QueueState.REBASING: 1}
        await self.manager.broadcast_queue_updated(self.queue_data, self.stats_data)

    def then_broadcast_should_be_sent_to_connection(self):
        assert self.fake_ws.send_count == 1
        message = self.fake_ws.last_sent
        assert message["type"] == "queue:updated"
        assert message["data"]["queue"] == self.queue_data
        assert message["data"]["stats"] == self.stats_data
