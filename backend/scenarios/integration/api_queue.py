"""API queue endpoint tests for Vedro scenarios.

Tests the /api/queue endpoints for queue status, active items, statistics,
and individual queue item retrieval.

Example:
    >>> vedro run scenarios/integration/api_queue.py
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import vedro
from scenarios.contexts.api_helpers import (
    create_test_app,
    create_test_jwt,
    create_test_queue_item,
)
from starlette.testclient import TestClient

# =============================================================================
# Queue Status Tests (/api/queue)
# =============================================================================


class Scenario__get_queue_status_returns_full_data(vedro.Scenario):
    """Test that /api/queue returns queue, history, and stats."""

    subject = "queue status endpoint returns full dashboard data"

    def given_app_with_queue_data(self):
        self.app, self.state = create_test_app()
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.token = create_test_jwt(self.state.settings)
        self.headers = {"Authorization": f"Bearer {self.token}"}

        # Setup mock queue data
        self.active_items = [
            create_test_queue_item(mr_iid=100, title="First MR", state="rebasing"),
            create_test_queue_item(mr_iid=101, title="Second MR", state="queued"),
        ]
        self.history_items = [
            create_test_queue_item(mr_iid=50, title="Old MR", state="merged"),
        ]
        self.current_stats = {"queued": 1, "rebasing": 1, "testing": 0, "merging": 0}
        self.dashboard_stats = MagicMock(
            total_in_queue=2,
            stats_window_days=7,
            merged_count=10,
            failed_count=2,
            success_rate=83.3,
            avg_wait_seconds=300,
            avg_processing_seconds=600,
        )

        self.state.queue_manager.get_active_queue = AsyncMock(return_value=self.active_items)
        self.state.queue_manager.get_recent_history = AsyncMock(return_value=self.history_items)
        self.state.queue_manager.get_queue_stats = AsyncMock(return_value=self.current_stats)
        self.state.queue_manager.get_dashboard_stats = AsyncMock(return_value=self.dashboard_stats)

    def when_queue_status_is_requested(self):
        self.response = self.client.get("/api/queue", headers=self.headers)

    def then_it_should_return_full_data(self):
        assert self.response.status_code == 200
        data = self.response.json()

        # Check queue section
        assert "queue" in data
        assert len(data["queue"]) == 2
        assert data["queue"][0]["mr_iid"] == 100
        assert data["queue"][0]["position"] == 1
        assert data["queue"][1]["mr_iid"] == 101
        assert data["queue"][1]["position"] == 2

        # Check history section
        assert "history" in data
        assert len(data["history"]) == 1
        assert data["history"][0]["mr_iid"] == 50

        # Check stats section
        assert "stats" in data
        assert "current" in data["stats"]
        assert "historical" in data["stats"]
        assert "timing" in data["stats"]
        assert data["stats"]["current"]["total"] == 2
        assert data["stats"]["historical"]["merged_count"] == 10


class Scenario__get_queue_status_requires_authentication(vedro.Scenario):
    """Test that /api/queue requires authentication."""

    subject = "queue status endpoint requires authentication"

    def given_app(self):
        self.app, self.state = create_test_app()
        self.client = TestClient(self.app, raise_server_exceptions=False)

    def when_queue_status_is_requested_without_token(self):
        self.response = self.client.get("/api/queue")

    def then_it_should_return_401(self):
        assert self.response.status_code == 401


# =============================================================================
# Active Queue Tests (/api/queue/active)
# =============================================================================


class Scenario__get_active_queue_returns_items(vedro.Scenario):
    """Test that /api/queue/active returns queue items with positions."""

    subject = "active queue endpoint returns items with positions"

    def given_app_with_active_items(self):
        self.app, self.state = create_test_app()
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.token = create_test_jwt(self.state.settings)
        self.headers = {"Authorization": f"Bearer {self.token}"}

        self.active_items = [
            create_test_queue_item(
                mr_iid=100,
                title="First MR",
                state="rebasing",
                is_hotfix=True,
            ),
            create_test_queue_item(mr_iid=101, title="Second MR", state="queued"),
            create_test_queue_item(mr_iid=102, title="Third MR", state="queued"),
        ]

        self.state.queue_manager.get_active_queue = AsyncMock(return_value=self.active_items)

    def when_active_queue_is_requested(self):
        self.response = self.client.get("/api/queue/active", headers=self.headers)

    def then_it_should_return_items_with_positions(self):
        assert self.response.status_code == 200
        data = self.response.json()

        assert "items" in data
        assert "count" in data
        assert data["count"] == 3
        assert len(data["items"]) == 3

        # Verify positions
        assert data["items"][0]["position"] == 1
        assert data["items"][0]["mr_iid"] == 100
        assert data["items"][0]["is_hotfix"] is True

        assert data["items"][1]["position"] == 2
        assert data["items"][2]["position"] == 3


class Scenario__get_active_queue_returns_empty_when_no_items(vedro.Scenario):
    """Test that /api/queue/active returns empty list when queue is empty."""

    subject = "active queue endpoint returns empty list when queue is empty"

    def given_app_with_empty_queue(self):
        self.app, self.state = create_test_app()
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.token = create_test_jwt(self.state.settings)
        self.headers = {"Authorization": f"Bearer {self.token}"}

        self.state.queue_manager.get_active_queue = AsyncMock(return_value=[])

    def when_active_queue_is_requested(self):
        self.response = self.client.get("/api/queue/active", headers=self.headers)

    def then_it_should_return_empty_list(self):
        assert self.response.status_code == 200
        data = self.response.json()

        assert data["items"] == []
        assert data["count"] == 0


class Scenario__get_active_queue_requires_authentication(vedro.Scenario):
    """Test that /api/queue/active requires authentication."""

    subject = "active queue endpoint requires authentication"

    def given_app(self):
        self.app, self.state = create_test_app()
        self.client = TestClient(self.app, raise_server_exceptions=False)

    def when_active_queue_is_requested_without_token(self):
        self.response = self.client.get("/api/queue/active")

    def then_it_should_return_401(self):
        assert self.response.status_code == 401


# =============================================================================
# Queue Stats Tests (/api/queue/stats)
# =============================================================================


class Scenario__get_queue_stats_returns_statistics(vedro.Scenario):
    """Test that /api/queue/stats returns current and historical statistics."""

    subject = "queue stats endpoint returns current and historical statistics"

    def given_app_with_stats(self):
        self.app, self.state = create_test_app()
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.token = create_test_jwt(self.state.settings)
        self.headers = {"Authorization": f"Bearer {self.token}"}

        self.current_stats = {"queued": 3, "rebasing": 1, "testing": 2, "merging": 0}
        self.dashboard_stats = MagicMock(
            total_in_queue=6,
            stats_window_days=7,
            merged_count=45,
            failed_count=5,
            success_rate=90.0,
            avg_wait_seconds=180,
            avg_processing_seconds=420,
        )

        self.state.queue_manager.get_queue_stats = AsyncMock(return_value=self.current_stats)
        self.state.queue_manager.get_dashboard_stats = AsyncMock(return_value=self.dashboard_stats)

    def when_queue_stats_are_requested(self):
        self.response = self.client.get("/api/queue/stats", headers=self.headers)

    def then_it_should_return_statistics(self):
        assert self.response.status_code == 200
        data = self.response.json()

        # Check current stats
        assert "current" in data
        assert data["current"]["total"] == 6
        assert data["current"]["by_status"]["queued"] == 3
        assert data["current"]["by_status"]["rebasing"] == 1

        # Check historical stats
        assert "historical" in data
        assert data["historical"]["window_days"] == 7
        assert data["historical"]["merged_count"] == 45
        assert data["historical"]["failed_count"] == 5
        assert data["historical"]["success_rate_percent"] == 90.0

        # Check timing stats
        assert "timing" in data
        assert data["timing"]["avg_wait_seconds"] == 180
        assert data["timing"]["avg_processing_seconds"] == 420


class Scenario__get_queue_stats_requires_authentication(vedro.Scenario):
    """Test that /api/queue/stats requires authentication."""

    subject = "queue stats endpoint requires authentication"

    def given_app(self):
        self.app, self.state = create_test_app()
        self.client = TestClient(self.app, raise_server_exceptions=False)

    def when_queue_stats_are_requested_without_token(self):
        self.response = self.client.get("/api/queue/stats")

    def then_it_should_return_401(self):
        assert self.response.status_code == 401


# =============================================================================
# Queue Item Tests (/api/queue/{mr_iid})
# =============================================================================


class Scenario__get_queue_item_returns_single_item(vedro.Scenario):
    """Test that /api/queue/{mr_iid} returns a single item with position."""

    subject = "queue item endpoint returns single item with position"

    def given_app_with_queue_item(self):
        self.app, self.state = create_test_app()
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.token = create_test_jwt(self.state.settings)
        self.headers = {"Authorization": f"Bearer {self.token}"}

        self.test_item = create_test_queue_item(
            mr_iid=42,
            title="Feature: Add user auth",
            author_name="Test Author",
            author_username="testauthor",
            state="testing",
            is_hotfix=False,
            labels=["feature", "auth"],
            target_branch="main",
            pipeline_id=12345,
            pipeline_status="running",
        )

        self.state.queue_manager.get_queue_item = AsyncMock(return_value=self.test_item)
        self.state.queue_manager.get_queue_position = AsyncMock(return_value=3)

    def when_queue_item_is_requested(self):
        self.response = self.client.get("/api/queue/42", headers=self.headers)

    def then_it_should_return_item_with_position(self):
        assert self.response.status_code == 200
        data = self.response.json()

        assert data["mr_iid"] == 42
        assert data["title"] == "Feature: Add user auth"
        assert data["author"]["name"] == "Test Author"
        assert data["author"]["username"] == "testauthor"
        assert data["state"] == "testing"
        assert data["is_hotfix"] is False
        assert data["labels"] == ["feature", "auth"]
        assert data["target_branch"] == "main"
        assert data["position"] == 3


class Scenario__get_queue_item_returns_404_for_missing(vedro.Scenario):
    """Test that /api/queue/{mr_iid} returns 404 for non-existent MR."""

    subject = "queue item endpoint returns 404 for non-existent MR"

    def given_app_with_no_item(self):
        self.app, self.state = create_test_app()
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.token = create_test_jwt(self.state.settings)
        self.headers = {"Authorization": f"Bearer {self.token}"}

        self.state.queue_manager.get_queue_item = AsyncMock(return_value=None)

    def when_nonexistent_item_is_requested(self):
        self.response = self.client.get("/api/queue/99999", headers=self.headers)

    def then_it_should_return_404(self):
        assert self.response.status_code == 404
        data = self.response.json()
        assert "not found" in data["detail"].lower()


class Scenario__get_queue_item_requires_authentication(vedro.Scenario):
    """Test that /api/queue/{mr_iid} requires authentication."""

    subject = "queue item endpoint requires authentication"

    def given_app(self):
        self.app, self.state = create_test_app()
        self.client = TestClient(self.app, raise_server_exceptions=False)

    def when_queue_item_is_requested_without_token(self):
        self.response = self.client.get("/api/queue/42")

    def then_it_should_return_401(self):
        assert self.response.status_code == 401
