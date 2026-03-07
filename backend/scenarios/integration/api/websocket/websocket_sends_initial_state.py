"""Test that WebSocket sends initial queue state on connection."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import vedro
from scenarios.contexts.api_helpers import (
    create_test_queue_item,
    created_test_app,
    created_test_jwt,
)
from scenarios.library import QueueState
from starlette.testclient import TestClient


class Scenario(vedro.Scenario):
    subject = "WebSocket sends initial queue state immediately after connection"

    def given_app_with_queue_data(self):
        self.app, self.state = created_test_app()
        self.client = TestClient(self.app)
        self.token = created_test_jwt(self.state.settings)

        now = datetime.now(UTC)
        self.state.queue_manager.add_item(
            create_test_queue_item(
                mr_iid=100,
                title="First MR",
                state=QueueState.REBASING,
                queued_at=now - timedelta(minutes=10),
            )
        )
        self.state.queue_manager.add_item(
            create_test_queue_item(
                mr_iid=101,
                title="Second MR",
                state=QueueState.QUEUED,
                queued_at=now,
            )
        )
        self.state.queue_manager.queue_stats = {
            QueueState.QUEUED: 1,
            QueueState.REBASING: 1,
            QueueState.TESTING: 0,
            QueueState.MERGING: 0,
        }

    def when_websocket_connects(self):
        with self.client.websocket_connect(f"/ws/queue?token={self.token}") as ws:
            self.initial_message = ws.receive_json()

    def then_should_receive_queue_updated_event(self):
        assert self.initial_message["type"] == "queue:updated"

    def and_should_contain_queue_items(self):
        queue = self.initial_message["data"]["queue"]
        assert len(queue) == 2
        assert queue[0]["mr_iid"] == 100
        assert queue[0]["title"] == "First MR"
        assert queue[0]["status"] == "rebasing"
        assert queue[0]["position"] == 1
        assert queue[1]["mr_iid"] == 101
        assert queue[1]["position"] == 2

    def and_should_contain_stats(self):
        stats = self.initial_message["data"]["stats"]
        assert stats["queued"] == 1
        assert stats["rebasing"] == 1
