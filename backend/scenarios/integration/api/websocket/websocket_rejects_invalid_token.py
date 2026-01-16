"""Test that WebSocket rejects connections with invalid JWT token."""

from __future__ import annotations

import vedro
from scenarios.contexts.api_helpers import (
    create_invalid_jwt,
    created_test_app,
)
from starlette.testclient import TestClient


class Scenario(vedro.Scenario):
    subject = "try to connect websocket with invalid token"

    def given_app_with_invalid_token(self):
        self.app, self.state = created_test_app()
        self.client = TestClient(self.app)
        self.token = create_invalid_jwt()

    def when_websocket_connects_with_invalid_token(self):
        self.exception = None
        self.connected = False
        try:
            with self.client.websocket_connect(f"/ws/queue?token={self.token}"):
                self.connected = True
        except Exception as e:
            self.exception = e

    def then_connection_should_be_rejected(self):
        # Connection should fail or close immediately
        assert self.connected is False or self.exception is not None
