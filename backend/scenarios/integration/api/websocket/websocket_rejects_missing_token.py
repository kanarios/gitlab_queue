"""Test that WebSocket rejects connections without token."""

from __future__ import annotations

import vedro
from scenarios.contexts.api_helpers import created_test_app
from starlette.testclient import TestClient


class Scenario(vedro.Scenario):
    subject = "try to connect websocket without token"

    def given_app_without_token(self):
        self.app, self.state = created_test_app()
        self.client = TestClient(self.app)

    def when_websocket_connects_without_token(self):
        self.exception = None
        self.connected = False
        try:
            with self.client.websocket_connect("/ws/queue"):
                self.connected = True
        except Exception as e:
            self.exception = e

    def then_connection_should_be_rejected(self):
        # Connection should fail or close immediately
        assert self.connected is False or self.exception is not None
