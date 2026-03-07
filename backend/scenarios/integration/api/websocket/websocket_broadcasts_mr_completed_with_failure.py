"""Test that WebSocketManager broadcasts mr:completed events with failure reason."""

from __future__ import annotations

from datetime import UTC, datetime

import vedro
from scenarios.fakes import FakeWebSocket
from scenarios.library import QueueState

from gitlab_queue.api.websocket import WebSocketManager


class Scenario(vedro.Scenario):
    subject = "WebSocketManager broadcasts mr:completed events with failure reason"

    def given_fake_websocket_connection(self):
        self.manager = WebSocketManager()
        self.fake_ws = FakeWebSocket()
        self.manager._connections.add(self.fake_ws)
        self.finished_at = datetime.now(UTC)

    async def when_failed_mr_completed_is_broadcast(self):
        await self.manager.broadcast_mr_completed(
            mr_iid=42,
            status=QueueState.FAILED,
            finished_at=self.finished_at,
            failure_reason="Merge conflict detected",
        )

    def then_broadcast_should_contain_failure_reason(self):
        assert self.fake_ws.send_count == 1
        message = self.fake_ws.last_sent
        assert message["type"] == "mr:completed"
        assert message["data"]["iid"] == 42
        assert message["data"]["status"] == "failed"
        assert message["data"]["failureReason"] == "Merge conflict detected"
