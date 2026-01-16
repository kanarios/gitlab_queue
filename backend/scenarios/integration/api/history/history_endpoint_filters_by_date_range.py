"""Test that /api/history filters by date range."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import vedro
from scenarios.contexts.api_helpers import (
    created_test_app,
    created_test_jwt,
)
from scenarios.schemas.status_code import OkStatusSchema
from starlette.testclient import TestClient


class Scenario(vedro.Scenario):
    subject = "history endpoint filters by date range"

    def given_app_with_mock_history(self):
        mock_result = MagicMock()
        mock_result.items = []
        mock_result.page = 1
        mock_result.per_page = 20
        mock_result.total = 0
        mock_result.total_pages = 0

        mock_uow = AsyncMock()
        mock_uow.history = MagicMock()
        mock_uow.history.get_history = AsyncMock(return_value=mock_result)
        mock_uow.__aenter__ = AsyncMock(return_value=mock_uow)
        mock_uow.__aexit__ = AsyncMock(return_value=None)

        import gitlab_queue.api.routes as routes_module

        self._original_uow = routes_module.UnitOfWork
        routes_module.UnitOfWork = MagicMock(return_value=mock_uow)
        self._mock_uow = mock_uow

        # Create app AFTER patching
        self.app, self.state = created_test_app()
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.token = created_test_jwt(self.state.settings)
        self.headers = {"Authorization": f"Bearer {self.token}"}

    def when_history_is_called_with_date_filter(self):
        today = datetime.now(UTC).date()
        yesterday = today - timedelta(days=1)

        self.response = self.client.get(
            f"/api/history?date_from={yesterday}&date_to={today}",
            headers=self.headers,
        )

    def then_it_should_pass_dates_to_repository(self):
        assert self.response.status_code == OkStatusSchema
        call_args = self._mock_uow.history.get_history.call_args
        assert call_args is not None
        assert call_args.kwargs.get("date_from") is not None
        assert call_args.kwargs.get("date_to") is not None

    def cleanup(self):
        import gitlab_queue.api.routes as routes_module

        routes_module.UnitOfWork = self._original_uow
