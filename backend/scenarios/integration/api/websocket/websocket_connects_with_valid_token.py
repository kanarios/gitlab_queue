"""Test that WebSocket accepts connections with valid JWT token."""

from __future__ import annotations

import vedro
from scenarios.contexts.api_helpers import (
    created_test_app,
    created_test_jwt,
)
from starlette.testclient import TestClient


class Scenario(vedro.Scenario):
    subject = "WebSocket accepts connections with valid JWT token"

    def given_app_with_valid_token(self):
        self.app, self.state = created_test_app()
        self.client = TestClient(self.app)
        self.token = created_test_jwt(self.state.settings)

    def when_websocket_connects(self):
        self.exception = None
        try:
            with self.client.websocket_connect(f"/ws/queue?token={self.token}") as ws:
                self.connected = True
                self.initial_message = ws.receive_json()
        except Exception as e:
            self.exception = e
            self.connected = False

    def then_connection_should_succeed(self):
        assert self.connected is True, f"Connection failed: {self.exception}"

    def and_should_receive_initial_state(self):
        assert self.initial_message["type"] == "queue:updated"
        assert "data" in self.initial_message
        assert "queue" in self.initial_message["data"]
        assert "stats" in self.initial_message["data"]
