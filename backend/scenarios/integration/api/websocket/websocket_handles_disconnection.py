"""Test that WebSocketManager handles client disconnections gracefully."""

from __future__ import annotations

import vedro
from scenarios.contexts.api_helpers import (
    created_test_app,
    created_test_jwt,
)
from starlette.testclient import TestClient


class Scenario(vedro.Scenario):
    subject = "WebSocketManager handles client disconnections gracefully"

    def given_connected_websocket(self):
        self.app, self.state = created_test_app()
        self.client = TestClient(self.app)
        self.token = created_test_jwt(self.state.settings)
        self.manager = self.state.websocket_manager

    def when_client_disconnects(self):
        with self.client.websocket_connect(f"/ws/queue?token={self.token}") as ws:
            ws.receive_json()  # Initial state
            self.count_while_connected = self.manager.connection_count
        # Context manager exits = disconnection
        self.count_after_disconnect = self.manager.connection_count

    def then_connection_should_be_removed(self):
        assert self.count_while_connected == 1
        assert self.count_after_disconnect == 0
