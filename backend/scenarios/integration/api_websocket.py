"""WebSocket API tests for Vedro scenarios.

Tests WebSocket connections, token validation, and real-time broadcasts.

Example:
    >>> vedro run scenarios/integration/api_websocket.py
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import vedro
from scenarios.contexts.api_helpers import (
    create_expired_jwt,
    create_invalid_jwt,
    create_test_app,
    create_test_jwt,
    create_test_queue_item,
)
from starlette.testclient import TestClient

from gitlab_queue.api.websocket import WebSocketManager

# =============================================================================
# WebSocket Connection Tests
# =============================================================================


class Scenario__websocket_connects_with_valid_token(vedro.Scenario):
    """Test that WebSocket accepts connections with valid JWT token."""

    subject = "WebSocket accepts connections with valid JWT token"

    def given_app_with_valid_token(self):
        self.app, self.state = create_test_app()
        self.client = TestClient(self.app)
        self.token = create_test_jwt(self.state.settings)

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

    def then_should_receive_initial_state(self):
        assert self.initial_message["type"] == "queue:updated"
        assert "data" in self.initial_message
        assert "queue" in self.initial_message["data"]
        assert "stats" in self.initial_message["data"]


class Scenario__websocket_rejects_invalid_token(vedro.Scenario):
    """Test that WebSocket rejects connections with invalid JWT token."""

    subject = "WebSocket rejects connections with invalid JWT token"

    def given_app_with_invalid_token(self):
        self.app, self.state = create_test_app()
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


class Scenario__websocket_rejects_expired_token(vedro.Scenario):
    """Test that WebSocket rejects connections with expired JWT token."""

    subject = "WebSocket rejects connections with expired JWT token"

    def given_app_with_expired_token(self):
        self.app, self.state = create_test_app()
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


class Scenario__websocket_rejects_missing_token(vedro.Scenario):
    """Test that WebSocket rejects connections without token."""

    subject = "WebSocket rejects connections without authentication token"

    def given_app_without_token(self):
        self.app, self.state = create_test_app()
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


# =============================================================================
# Initial State Tests
# =============================================================================


class Scenario__websocket_sends_initial_state(vedro.Scenario):
    """Test that WebSocket sends initial queue state on connection."""

    subject = "WebSocket sends initial queue state immediately after connection"

    def given_app_with_queue_data(self):
        self.app, self.state = create_test_app()
        self.client = TestClient(self.app)
        self.token = create_test_jwt(self.state.settings)

        # Setup mock queue data
        self.test_items = [
            create_test_queue_item(mr_iid=100, title="First MR", state="rebasing"),
            create_test_queue_item(mr_iid=101, title="Second MR", state="queued"),
        ]
        self.test_stats = {
            "queued": 1,
            "rebasing": 1,
            "testing": 0,
            "merging": 0,
        }

        self.state.queue_manager.get_active_queue = AsyncMock(return_value=self.test_items)
        self.state.queue_manager.get_queue_stats = AsyncMock(return_value=self.test_stats)

    def when_websocket_connects(self):
        with self.client.websocket_connect(f"/ws/queue?token={self.token}") as ws:
            self.initial_message = ws.receive_json()

    def then_should_receive_queue_updated_event(self):
        assert self.initial_message["type"] == "queue:updated"

    def then_should_contain_queue_items(self):
        queue = self.initial_message["data"]["queue"]
        assert len(queue) == 2
        assert queue[0]["mr_iid"] == 100
        assert queue[0]["title"] == "First MR"
        assert queue[0]["status"] == "rebasing"
        assert queue[0]["position"] == 1
        assert queue[1]["mr_iid"] == 101
        assert queue[1]["position"] == 2

    def then_should_contain_stats(self):
        stats = self.initial_message["data"]["stats"]
        assert stats["queued"] == 1
        assert stats["rebasing"] == 1


# =============================================================================
# Broadcast Tests
# =============================================================================


class Scenario__websocket_broadcasts_queue_updated(vedro.Scenario):
    """Test that WebSocketManager broadcasts queue:updated events."""

    subject = "WebSocketManager broadcasts queue:updated events to connected clients"

    def given_mock_websocket_connection(self):
        # Create a mock WebSocket to test broadcast functionality
        self.manager = WebSocketManager()
        self.mock_ws = MagicMock()
        self.mock_ws.send_json = AsyncMock()
        self.mock_ws.client_state = MagicMock()
        # Simulate connected state
        self.mock_ws.client_state.name = "CONNECTED"
        self.manager._connections.append(self.mock_ws)

    async def when_queue_updated_is_broadcast(self):
        self.queue_data = [{"mr_iid": 42, "title": "Test", "status": "rebasing"}]
        self.stats_data = {"queued": 0, "rebasing": 1}
        await self.manager.broadcast_queue_updated(self.queue_data, self.stats_data)

    def then_broadcast_should_be_sent_to_connection(self):
        self.mock_ws.send_json.assert_called_once()
        call_args = self.mock_ws.send_json.call_args[0][0]
        assert call_args["type"] == "queue:updated"
        assert call_args["data"]["queue"] == self.queue_data
        assert call_args["data"]["stats"] == self.stats_data


class Scenario__websocket_broadcasts_mr_status_changed(vedro.Scenario):
    """Test that WebSocketManager broadcasts mr:status_changed events."""

    subject = "WebSocketManager broadcasts mr:status_changed events to connected clients"

    def given_mock_websocket_connection(self):
        # Create a mock WebSocket to test broadcast functionality
        self.manager = WebSocketManager()
        self.mock_ws = MagicMock()
        self.mock_ws.send_json = AsyncMock()
        self.mock_ws.client_state = MagicMock()
        self.mock_ws.client_state.name = "CONNECTED"
        self.manager._connections.append(self.mock_ws)

    async def when_mr_status_changed_is_broadcast(self):
        await self.manager.broadcast_mr_status_changed(42, "queued", "rebasing")

    def then_broadcast_should_contain_status_change(self):
        self.mock_ws.send_json.assert_called_once()
        call_args = self.mock_ws.send_json.call_args[0][0]
        assert call_args["type"] == "mr:status_changed"
        assert call_args["data"]["iid"] == 42
        assert call_args["data"]["oldStatus"] == "queued"
        assert call_args["data"]["newStatus"] == "rebasing"


class Scenario__websocket_broadcasts_mr_completed(vedro.Scenario):
    """Test that WebSocketManager broadcasts mr:completed events."""

    subject = "WebSocketManager broadcasts mr:completed events to connected clients"

    def given_mock_websocket_connection(self):
        # Create a mock WebSocket to test broadcast functionality
        self.manager = WebSocketManager()
        self.mock_ws = MagicMock()
        self.mock_ws.send_json = AsyncMock()
        self.mock_ws.client_state = MagicMock()
        self.mock_ws.client_state.name = "CONNECTED"
        self.manager._connections.append(self.mock_ws)
        self.finished_at = datetime.now(UTC)

    async def when_mr_completed_is_broadcast(self):
        await self.manager.broadcast_mr_completed(
            mr_iid=42,
            status="merged",
            finished_at=self.finished_at,
        )

    def then_broadcast_should_contain_completion_info(self):
        self.mock_ws.send_json.assert_called_once()
        call_args = self.mock_ws.send_json.call_args[0][0]
        assert call_args["type"] == "mr:completed"
        assert call_args["data"]["iid"] == 42
        assert call_args["data"]["status"] == "merged"
        assert call_args["data"]["finishedAt"] is not None


class Scenario__websocket_broadcasts_mr_completed_with_failure(vedro.Scenario):
    """Test that WebSocketManager broadcasts mr:completed events with failure reason."""

    subject = "WebSocketManager broadcasts mr:completed events with failure reason"

    def given_mock_websocket_connection(self):
        # Create a mock WebSocket to test broadcast functionality
        self.manager = WebSocketManager()
        self.mock_ws = MagicMock()
        self.mock_ws.send_json = AsyncMock()
        self.mock_ws.client_state = MagicMock()
        self.mock_ws.client_state.name = "CONNECTED"
        self.manager._connections.append(self.mock_ws)
        self.finished_at = datetime.now(UTC)

    async def when_failed_mr_completed_is_broadcast(self):
        await self.manager.broadcast_mr_completed(
            mr_iid=42,
            status="failed",
            finished_at=self.finished_at,
            failure_reason="Merge conflict detected",
        )

    def then_broadcast_should_contain_failure_reason(self):
        self.mock_ws.send_json.assert_called_once()
        call_args = self.mock_ws.send_json.call_args[0][0]
        assert call_args["type"] == "mr:completed"
        assert call_args["data"]["iid"] == 42
        assert call_args["data"]["status"] == "failed"
        assert call_args["data"]["failureReason"] == "Merge conflict detected"


# =============================================================================
# Multiple Client Tests
# =============================================================================


class Scenario__websocket_handles_multiple_clients(vedro.Scenario):
    """Test that WebSocketManager handles multiple connected clients."""

    subject = "WebSocketManager handles multiple simultaneous client connections"

    def given_app_with_websocket_manager(self):
        self.app, self.state = create_test_app()
        self.client = TestClient(self.app)
        self.token = create_test_jwt(self.state.settings)
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

    def then_connection_count_should_decrease_on_disconnect(self):
        assert self.count_after_second_disconnect == 1
        assert self.count_after_all_disconnect == 0


# =============================================================================
# Disconnection Handling Tests
# =============================================================================


class Scenario__websocket_handles_disconnection(vedro.Scenario):
    """Test that WebSocketManager handles client disconnections gracefully."""

    subject = "WebSocketManager handles client disconnections gracefully"

    def given_connected_websocket(self):
        self.app, self.state = create_test_app()
        self.client = TestClient(self.app)
        self.token = create_test_jwt(self.state.settings)
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


class Scenario__websocket_manager_removes_failed_connections_on_broadcast(vedro.Scenario):
    """Test that WebSocketManager removes failed connections during broadcast."""

    subject = "WebSocketManager removes disconnected clients during broadcast"

    def given_websocket_manager_with_mock_connection(self):
        self.app, self.state = create_test_app()
        self.manager = self.state.websocket_manager

        # Create a mock WebSocket that will fail on send
        self.mock_ws = MagicMock()
        self.mock_ws.send_json = AsyncMock(side_effect=Exception("Connection closed"))

        # Add directly to manager
        self.manager._connections.add(self.mock_ws)
        self.count_before = self.manager.connection_count

    async def when_broadcast_is_attempted(self):
        await self.manager.broadcast({"type": "test", "data": {}})
        self.count_after = self.manager.connection_count

    def then_failed_connection_should_be_removed(self):
        assert self.count_before == 1
        assert self.count_after == 0


# =============================================================================
# Queue Item Serialization Tests
# =============================================================================


class Scenario__websocket_serializes_queue_items_correctly(vedro.Scenario):
    """Test that queue items are serialized correctly for WebSocket."""

    subject = "WebSocket serializes queue items with all required fields"

    def given_app_with_detailed_queue_item(self):
        self.app, self.state = create_test_app()
        self.client = TestClient(self.app)
        self.token = create_test_jwt(self.state.settings)

        # Create detailed queue item
        self.test_item = create_test_queue_item(
            mr_iid=42,
            title="Feature: Add user auth",
            author_name="Test Author",
            author_username="testauthor",
            author_avatar="https://example.com/avatar.png",
            state="testing",
            is_hotfix=True,
            labels=["feature", "auth"],
            target_branch="main",
            pipeline_id=12345,
            pipeline_status="running",
        )

        self.state.queue_manager.get_active_queue = AsyncMock(return_value=[self.test_item])
        self.state.queue_manager.get_queue_stats = AsyncMock(return_value={"testing": 1})

    def when_websocket_receives_initial_state(self):
        with self.client.websocket_connect(f"/ws/queue?token={self.token}") as ws:
            self.message = ws.receive_json()

    def then_item_should_have_all_fields(self):
        item = self.message["data"]["queue"][0]

        assert item["mr_iid"] == 42
        assert item["title"] == "Feature: Add user auth"
        assert item["author"]["name"] == "Test Author"
        assert item["author"]["username"] == "testauthor"
        assert item["author"]["avatar_url"] == "https://example.com/avatar.png"
        assert item["status"] == "testing"
        assert item["is_hotfix"] is True
        assert item["labels"] == ["feature", "auth"]
        assert item["target_branch"] == "main"
        assert item["position"] == 1

    def then_item_should_have_pipeline_info(self):
        item = self.message["data"]["queue"][0]

        assert item["pipeline"]["id"] == 12345
        assert item["pipeline"]["status"] == "running"


class Scenario__websocket_serializes_error_info(vedro.Scenario):
    """Test that queue items with errors are serialized correctly."""

    subject = "WebSocket serializes queue items with error information"

    def given_app_with_errored_queue_item(self):
        self.app, self.state = create_test_app()
        self.client = TestClient(self.app)
        self.token = create_test_jwt(self.state.settings)

        # Create queue item with error
        self.test_item = create_test_queue_item(
            mr_iid=42,
            title="MR with errors",
            state="queued",
            last_error="Rebase failed: merge conflict",
            retry_count=2,
        )

        self.state.queue_manager.get_active_queue = AsyncMock(return_value=[self.test_item])
        self.state.queue_manager.get_queue_stats = AsyncMock(return_value={"queued": 1})

    def when_websocket_receives_initial_state(self):
        with self.client.websocket_connect(f"/ws/queue?token={self.token}") as ws:
            self.message = ws.receive_json()

    def then_item_should_have_error_info(self):
        item = self.message["data"]["queue"][0]

        assert item["last_error"] == "Rebase failed: merge conflict"
        assert item["retry_count"] == 2
