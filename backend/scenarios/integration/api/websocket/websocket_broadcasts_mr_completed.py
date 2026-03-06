"""Test that WebSocketManager broadcasts mr:completed events."""

from __future__ import annotations

from datetime import UTC, datetime

import vedro
from scenarios.fakes import FakeWebSocket
from scenarios.library import QueueState

from gitlab_queue.api.websocket import WebSocketManager


class Scenario(vedro.Scenario):
    subject = "WebSocketManager broadcasts mr:completed events to connected clients"

    def given_fake_websocket_connection(self):
        self.manager = WebSocketManager()
        self.fake_ws = FakeWebSocket()
        self.manager._connections.add(self.fake_ws)
        self.finished_at = datetime.now(UTC)

    async def when_mr_completed_is_broadcast(self):
        await self.manager.broadcast_mr_completed(
            mr_iid=42,
            status=QueueState.MERGED,
            finished_at=self.finished_at,
        )

    def then_broadcast_should_contain_completion_info(self):
        assert self.fake_ws.send_count == 1
        message = self.fake_ws.last_sent
        assert message["type"] == "mr:completed"
        assert message["data"]["iid"] == 42
        assert message["data"]["status"] == "merged"
        assert message["data"]["finishedAt"] is not None
