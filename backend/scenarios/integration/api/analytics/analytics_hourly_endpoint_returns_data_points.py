"""Test that /api/analytics/hourly returns hourly data points."""

from __future__ import annotations

from datetime import UTC, datetime

import vedro
from scenarios.contexts.api_helpers import (
    created_test_app,
    created_test_jwt,
)
from scenarios.fakes import AnalyticsMetrics, FakeAnalyticsRepo, FakeUnitOfWork
from scenarios.schemas.status_code import OkStatusSchema
from starlette.testclient import TestClient


class Scenario(vedro.Scenario):
    subject = "analytics hourly endpoint returns data points"

    def given_app_with_hourly_data(self):
        self.app, self.state = created_test_app()
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.token = created_test_jwt(self.state.settings)
        self.headers = {"Authorization": f"Bearer {self.token}"}

        now = datetime.now(UTC)
        hourly_data = [
            {"timestamp": (now).isoformat(), "queue_depth": 5, "processed_count": 3},
            {"timestamp": (now).isoformat(), "queue_depth": 4, "processed_count": 2},
        ]

        analytics_repo = FakeAnalyticsRepo(
            metrics_result=AnalyticsMetrics(hourly_trend=hourly_data),
        )
        uow = FakeUnitOfWork(analytics=analytics_repo)

        self.state.uow_factory = lambda db: uow

    def when_hourly_endpoint_is_called(self):
        self.response = self.client.get(
            "/api/analytics/hourly",
            headers=self.headers,
        )

    def then_it_should_return_data_points(self):
        assert self.response.status_code == OkStatusSchema
        data = self.response.json()

        assert "data" in data
        assert "hours" in data
        assert data["hours"] == 24  # default

        # Verify data point structure
        if len(data["data"]) > 0:
            point = data["data"][0]
            assert "timestamp" in point
            assert "queue_depth" in point
            assert "processed_count" in point
