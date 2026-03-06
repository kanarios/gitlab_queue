"""Test that /api/analytics/summary returns metrics."""

from __future__ import annotations

import vedro
from scenarios.contexts.api_helpers import (
    created_test_app,
    created_test_jwt,
)
from scenarios.fakes import FakeHistoryRepo, FakeUnitOfWork, HistoryStatsResult
from scenarios.schemas.status_code import OkStatusSchema
from starlette.testclient import TestClient


class Scenario(vedro.Scenario):
    subject = "analytics summary endpoint returns aggregate metrics"

    def given_app_with_analytics_data(self):
        self.app, self.state = created_test_app()
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.token = created_test_jwt(self.state.settings)
        self.headers = {"Authorization": f"Bearer {self.token}"}

        history_repo = FakeHistoryRepo(
            stats_for_period_result=HistoryStatsResult(
                total_processed=100,
                success_count=90,
                failed_count=5,
                conflict_count=3,
                timeout_count=2,
                avg_wait_time_seconds=300,
                avg_processing_time_seconds=600,
            ),
        )
        uow = FakeUnitOfWork(history=history_repo)

        self.state.uow_factory = lambda db: uow

    def when_summary_endpoint_is_called(self):
        self.response = self.client.get(
            "/api/analytics/summary",
            headers=self.headers,
        )

    def then_it_should_return_metrics(self):
        assert self.response.status_code == OkStatusSchema
        data = self.response.json()

        assert "total_processed" in data
        assert "avg_wait_time_seconds" in data
        assert "avg_processing_time_seconds" in data
        assert "success_rate_percent" in data
        assert "daily_throughput" in data
        assert "period_days" in data

        assert data["total_processed"] == 100
        assert data["success_rate_percent"] == 90.0
        assert data["period_days"] == 7  # default
