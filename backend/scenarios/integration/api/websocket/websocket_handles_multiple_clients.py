"""Test that WebSocketManager handles multiple connected clients."""

from __future__ import annotations

import vedro
from scenarios.contexts.api_helpers import (
    created_test_app,
    created_test_jwt,
)
from starlette.testclient import TestClient


class Scenario(vedro.Scenario):
    subject = "WebSocketManager handles multiple simultaneous client connections"

    def given_app_with_websocket_manager(self):
        self.app, self.state = created_test_app()
        self.client = TestClient(self.app)
        self.token = created_test_jwt(self.state.settings)
        self.manager = self.state.websocket_manager

    def when_multiple_clients_connect(self):
        # Connect first client
        with self.client.websocket_connect(f"/ws/queue?token={self.token}") as ws1:
            ws1.receive_json()  # Initial state
            self.count_after_first = self.manager.connection_count

            # Connect second client
            with self.client.websocket_connect(f"/ws/queue?token={self.token}") as ws2:
                ws2.receive_json()  # Initial state
                self.count_after_second = self.manager.connection_count

            # Second disconnected
            self.count_after_second_disconnect = self.manager.connection_count

        # First disconnected
        self.count_after_all_disconnect = self.manager.connection_count

    def then_connection_count_should_increase(self):
        assert self.count_after_first == 1
        assert self.count_after_second == 2

    def and_connection_count_should_decrease_on_disconnect(self):
        assert self.count_after_second_disconnect == 1
        assert self.count_after_all_disconnect == 0
