"""Test that /api/analytics/hourly respects hours parameter."""

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
    subject = "analytics hourly endpoint respects hours parameter"

    def given_app(self):
        self.app, self.state = created_test_app()
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.token = created_test_jwt(self.state.settings)
        self.headers = {"Authorization": f"Bearer {self.token}"}

        mock_metrics = MagicMock()
        mock_metrics.hourly_trend = []

        mock_uow = AsyncMock()
        mock_uow.analytics = AsyncMock()
        mock_uow.analytics.get_metrics = AsyncMock(return_value=mock_metrics)
        mock_uow.__aenter__ = AsyncMock(return_value=mock_uow)
        mock_uow.__aexit__ = AsyncMock(return_value=None)

        import gitlab_queue.api.routes as routes_module

        self._original_uow = routes_module.UnitOfWork
        routes_module.UnitOfWork = MagicMock(return_value=mock_uow)

    def when_hourly_is_called_with_hours(self):
        self.response = self.client.get(
            "/api/analytics/hourly?hours=48",
            headers=self.headers,
        )

    def then_it_should_return_custom_hours(self):
        assert self.response.status_code == OkStatusSchema
        data = self.response.json()
        assert data["hours"] == 48

    def cleanup(self):
        import gitlab_queue.api.routes as routes_module

        routes_module.UnitOfWork = self._original_uow
