"""Test that queue items with errors are serialized correctly."""

from __future__ import annotations

from unittest.mock import AsyncMock

import vedro
from scenarios.library import QueueState
from scenarios.contexts.api_helpers import (
    create_test_queue_item,
    created_test_app,
    created_test_jwt,
)
from starlette.testclient import TestClient


class Scenario(vedro.Scenario):
    subject = "WebSocket serializes queue items with error information"

    def given_app_with_errored_queue_item(self):
        self.app, self.state = created_test_app()
        self.client = TestClient(self.app)
        self.token = created_test_jwt(self.state.settings)

        # Create queue item with error
        self.test_item = create_test_queue_item(
            mr_iid=42,
            title="MR with errors",
            state=QueueState.QUEUED,
            last_error="Rebase failed: merge conflict",
            retry_count=2,
        )

        self.state.queue_manager.get_active_queue = AsyncMock(return_value=[self.test_item])
        self.state.queue_manager.get_queue_stats = AsyncMock(return_value={QueueState.QUEUED: 1})

    def when_websocket_receives_initial_state(self):
        with self.client.websocket_connect(f"/ws/queue?token={self.token}") as ws:
            self.message = ws.receive_json()

    def then_item_should_have_error_info(self):
        item = self.message["data"]["queue"][0]

        assert item["last_error"] == "Rebase failed: merge conflict"
        assert item["retry_count"] == 2
