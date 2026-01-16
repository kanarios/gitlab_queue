"""Test that /api/analytics/summary returns metrics."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import vedro
from scenarios.contexts.api_helpers import (
    created_test_app,
    created_test_jwt,
)
from scenarios.schemas.status_code import OkStatusSchema
from starlette.testclient import TestClient


class Scenario(vedro.Scenario):
    subject = "analytics summary endpoint returns aggregate metrics"

    def given_app_with_analytics_data(self):
        self.app, self.state = created_test_app()
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.token = created_test_jwt(self.state.settings)
        self.headers = {"Authorization": f"Bearer {self.token}"}

        # Mock stats
        mock_stats = MagicMock()
        mock_stats.total_processed = 100
        mock_stats.success_count = 90
        mock_stats.failed_count = 5
        mock_stats.conflict_count = 3
        mock_stats.timeout_count = 2
        mock_stats.avg_wait_time_seconds = 300
        mock_stats.avg_processing_time_seconds = 600

        mock_uow = AsyncMock()
        mock_uow.history = AsyncMock()
        mock_uow.history.get_stats_for_period = AsyncMock(return_value=mock_stats)
        mock_uow.__aenter__ = AsyncMock(return_value=mock_uow)
        mock_uow.__aexit__ = AsyncMock(return_value=None)

        import gitlab_queue.api.routes as routes_module

        self._original_uow = routes_module.UnitOfWork
        routes_module.UnitOfWork = MagicMock(return_value=mock_uow)

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

    def cleanup(self):
        import gitlab_queue.api.routes as routes_module

        routes_module.UnitOfWork = self._original_uow
