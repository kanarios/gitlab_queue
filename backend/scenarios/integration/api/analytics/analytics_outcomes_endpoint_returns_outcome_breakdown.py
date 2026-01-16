"""Test that /api/analytics/outcomes returns outcome breakdown."""

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
    subject = "analytics outcomes endpoint returns outcome breakdown"

    def given_app_with_outcomes_data(self):
        self.app, self.state = created_test_app()
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.token = created_test_jwt(self.state.settings)
        self.headers = {"Authorization": f"Bearer {self.token}"}

        mock_stats = MagicMock()
        mock_stats.total_processed = 100
        mock_stats.success_count = 80
        mock_stats.failed_count = 10
        mock_stats.conflict_count = 7
        mock_stats.timeout_count = 3

        mock_uow = AsyncMock()
        mock_uow.history = AsyncMock()
        mock_uow.history.get_stats_for_period = AsyncMock(return_value=mock_stats)
        mock_uow.__aenter__ = AsyncMock(return_value=mock_uow)
        mock_uow.__aexit__ = AsyncMock(return_value=None)

        import gitlab_queue.api.routes as routes_module

        self._original_uow = routes_module.UnitOfWork
        routes_module.UnitOfWork = MagicMock(return_value=mock_uow)

    def when_outcomes_endpoint_is_called(self):
        self.response = self.client.get(
            "/api/analytics/outcomes",
            headers=self.headers,
        )

    def then_it_should_return_breakdown(self):
        assert self.response.status_code == OkStatusSchema
        data = self.response.json()

        assert "outcomes" in data
        assert "total" in data
        assert "period_days" in data

        # Verify outcome structure
        outcomes = data["outcomes"]
        assert len(outcomes) > 0

        for outcome in outcomes:
            assert "name" in outcome
            assert "count" in outcome
            assert "percentage" in outcome

    def cleanup(self):
        import gitlab_queue.api.routes as routes_module

        routes_module.UnitOfWork = self._original_uow
