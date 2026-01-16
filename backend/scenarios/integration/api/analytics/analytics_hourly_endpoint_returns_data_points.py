"""Test that /api/analytics/hourly returns hourly data points."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import vedro
from scenarios.contexts.api_helpers import (
    created_test_app,
    created_test_jwt,
)
from scenarios.schemas.status_code import OkStatusSchema
from starlette.testclient import TestClient


class Scenario(vedro.Scenario):
    subject = "analytics hourly endpoint returns data points"

    def given_app_with_hourly_data(self):
        self.app, self.state = created_test_app()
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.token = created_test_jwt(self.state.settings)
        self.headers = {"Authorization": f"Bearer {self.token}"}

        # Mock hourly data
        now = datetime.now(UTC)
        hourly_data = [
            {"timestamp": (now).isoformat(), "queue_depth": 5, "processed_count": 3},
            {"timestamp": (now).isoformat(), "queue_depth": 4, "processed_count": 2},
        ]

        mock_metrics = MagicMock()
        mock_metrics.hourly_trend = hourly_data

        mock_uow = AsyncMock()
        mock_uow.analytics = AsyncMock()
        mock_uow.analytics.get_metrics = AsyncMock(return_value=mock_metrics)
        mock_uow.__aenter__ = AsyncMock(return_value=mock_uow)
        mock_uow.__aexit__ = AsyncMock(return_value=None)

        import gitlab_queue.api.routes as routes_module

        self._original_uow = routes_module.UnitOfWork
        routes_module.UnitOfWork = MagicMock(return_value=mock_uow)

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

    def cleanup(self):
        import gitlab_queue.api.routes as routes_module

        routes_module.UnitOfWork = self._original_uow
