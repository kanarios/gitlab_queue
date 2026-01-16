"""Test that WebSocket rejects connections with expired JWT token."""

from __future__ import annotations

import vedro
from scenarios.contexts.api_helpers import (
    create_expired_jwt,
    created_test_app,
)
from starlette.testclient import TestClient


class Scenario(vedro.Scenario):
    subject = "try to connect websocket with expired token"

    def given_app_with_expired_token(self):
        self.app, self.state = created_test_app()
        self.client = TestClient(self.app)
        self.token = create_expired_jwt(self.state.settings)

    def when_websocket_connects_with_expired_token(self):
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
