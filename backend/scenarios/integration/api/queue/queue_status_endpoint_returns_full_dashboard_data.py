"""Test that /api/queue returns queue, history, and stats."""

from __future__ import annotations

import vedro
from scenarios.contexts.api_helpers import (
    create_test_queue_item,
    created_test_app,
    created_test_jwt,
)
from scenarios.library import QueueState
from scenarios.schemas.status_code import OkStatusSchema
from starlette.testclient import TestClient

from gitlab_queue.models.queue_item import DashboardStats


class Scenario(vedro.Scenario):
    subject = "queue status endpoint returns full dashboard data"

    def given_app_with_queue_data(self):
        self.app, self.state = created_test_app()
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.token = created_test_jwt(self.state.settings)
        self.headers = {"Authorization": f"Bearer {self.token}"}

        # Setup queue data via FakeQueueManager
        self.active_items = [
            create_test_queue_item(mr_iid=100, title="First MR", state=QueueState.REBASING),
            create_test_queue_item(mr_iid=101, title="Second MR", state=QueueState.QUEUED),
        ]
        for item in self.active_items:
            self.state.queue_manager.add_item(item)

        self.state.queue_manager.recent_history = [
            create_test_queue_item(mr_iid=50, title="Old MR", state=QueueState.MERGED),
        ]
        self.state.queue_manager.queue_stats = {
            QueueState.QUEUED: 1,
            QueueState.REBASING: 1,
            QueueState.TESTING: 0,
            QueueState.MERGING: 0,
        }
        self.state.queue_manager.dashboard_stats = DashboardStats(
            total_in_queue=2,
            stats_window_days=7,
            merged_count=10,
            failed_count=2,
            success_rate=83.3,
            avg_wait_seconds=300,
            avg_processing_seconds=600,
        )

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
