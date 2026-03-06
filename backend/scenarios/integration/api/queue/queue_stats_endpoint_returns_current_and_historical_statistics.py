"""Test that /api/queue/stats returns current and historical statistics."""

from __future__ import annotations

import vedro
from scenarios.contexts.api_helpers import (
    created_test_app,
    created_test_jwt,
)
from scenarios.library import QueueState
from scenarios.schemas.status_code import OkStatusSchema
from starlette.testclient import TestClient

from gitlab_queue.models.queue_item import DashboardStats


class Scenario(vedro.Scenario):
    subject = "queue stats endpoint returns current and historical statistics"

    def given_app_with_stats(self):
        self.app, self.state = created_test_app()
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.token = created_test_jwt(self.state.settings)
        self.headers = {"Authorization": f"Bearer {self.token}"}

        self.state.queue_manager.queue_stats = {
            QueueState.QUEUED: 3,
            QueueState.REBASING: 1,
            QueueState.TESTING: 2,
            QueueState.MERGING: 0,
        }
        self.state.queue_manager.dashboard_stats = DashboardStats(
            total_in_queue=6,
            stats_window_days=7,
            merged_count=45,
            failed_count=5,
            success_rate=90.0,
            avg_wait_seconds=180,
            avg_processing_seconds=420,
        )

    def when_queue_stats_are_requested(self):
        self.response = self.client.get("/api/queue/stats", headers=self.headers)

    def then_it_should_return_statistics(self):
        assert self.response.status_code == OkStatusSchema
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
