"""Test that /api/analytics/summary respects days parameter."""

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
    subject = "analytics summary endpoint respects days parameter"

    def given_app(self):
        self.app, self.state = created_test_app()
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.token = created_test_jwt(self.state.settings)
        self.headers = {"Authorization": f"Bearer {self.token}"}

        mock_stats = MagicMock()
        mock_stats.total_processed = 50
        mock_stats.success_count = 45
        mock_stats.avg_wait_time_seconds = 200
        mock_stats.avg_processing_time_seconds = 400

        mock_uow = AsyncMock()
        mock_uow.history = AsyncMock()
        mock_uow.history.get_stats_for_period = AsyncMock(return_value=mock_stats)
        mock_uow.__aenter__ = AsyncMock(return_value=mock_uow)
        mock_uow.__aexit__ = AsyncMock(return_value=None)

        import gitlab_queue.api.routes as routes_module

        self._original_uow = routes_module.UnitOfWork
        routes_module.UnitOfWork = MagicMock(return_value=mock_uow)
        self._mock_uow = mock_uow

    def when_summary_is_called_with_days(self):
        self.response = self.client.get(
            "/api/analytics/summary?days=30",
            headers=self.headers,
        )

    def then_it_should_use_custom_days(self):
        assert self.response.status_code == OkStatusSchema
        data = self.response.json()
        assert data["period_days"] == 30

    def cleanup(self):
        import gitlab_queue.api.routes as routes_module

        routes_module.UnitOfWork = self._original_uow
