"""Test that /api/queue returns queue, history, and stats."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import vedro
from scenarios.contexts.api_helpers import (
    create_test_queue_item,
    created_test_app,
    created_test_jwt,
)
from scenarios.library import QueueState
from scenarios.schemas.status_code import OkStatusSchema
from starlette.testclient import TestClient


class Scenario(vedro.Scenario):
    subject = "queue status endpoint returns full dashboard data"

    def given_app_with_queue_data(self):
        self.app, self.state = created_test_app()
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.token = created_test_jwt(self.state.settings)
        self.headers = {"Authorization": f"Bearer {self.token}"}

        # Setup mock queue data
        self.active_items = [
            create_test_queue_item(mr_iid=100, title="First MR", state=QueueState.REBASING),
            create_test_queue_item(mr_iid=101, title="Second MR", state=QueueState.QUEUED),
        ]
        self.history_items = [
            create_test_queue_item(mr_iid=50, title="Old MR", state=QueueState.MERGED),
        ]
        self.current_stats = {
            QueueState.QUEUED: 1,
            QueueState.REBASING: 1,
            QueueState.TESTING: 0,
            QueueState.MERGING: 0,
        }
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
        assert self.response.status_code == OkStatusSchema
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
