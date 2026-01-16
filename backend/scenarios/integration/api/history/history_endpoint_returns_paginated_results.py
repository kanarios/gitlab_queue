"""Test that /api/history returns paginated results."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import vedro
from scenarios.contexts.api_helpers import (
    create_test_history_items,
    created_test_app,
    created_test_jwt,
)
from scenarios.schemas.status_code import OkStatusSchema
from starlette.testclient import TestClient

from ._helpers import _queue_item_to_history_model

# Note: Starlette's BaseHTTPMiddleware has known issues with async context
# handling when combined with TestClient. Using raise_server_exceptions=False
# to work around this issue for authenticated endpoints.


class Scenario(vedro.Scenario):
    subject = "history endpoint returns paginated results"

    def given_app_with_history_data(self):
        # Mock history repository
        history_items = create_test_history_items(count=15)
        mock_result = MagicMock()
        mock_result.items = [_queue_item_to_history_model(item) for item in history_items[:10]]
        mock_result.page = 1
        mock_result.per_page = 10
        mock_result.total = 15
        mock_result.total_pages = 2

        # Create a mock UnitOfWork context manager
        mock_uow = AsyncMock()
        mock_uow.history = MagicMock()
        mock_uow.history.get_history = AsyncMock(return_value=mock_result)
        mock_uow.__aenter__ = AsyncMock(return_value=mock_uow)
        mock_uow.__aexit__ = AsyncMock(return_value=None)

        # Patch UnitOfWork BEFORE creating the app
        import gitlab_queue.api.routes as routes_module

        self._original_uow = routes_module.UnitOfWork
        routes_module.UnitOfWork = MagicMock(return_value=mock_uow)

        # Create app and client AFTER patching
        self.app, self.state = created_test_app()
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.token = created_test_jwt(self.state.settings)
        self.headers = {"Authorization": f"Bearer {self.token}"}

    def when_history_endpoint_is_called(self):
        self.response = self.client.get(
            "/api/history?page=1&per_page=10",
            headers=self.headers,
        )

    def then_it_should_return_paginated_data(self):
        assert self.response.status_code == OkStatusSchema
        data = self.response.json()

        assert "items" in data
        assert "pagination" in data
        assert len(data["items"]) <= 10

        pagination = data["pagination"]
        assert pagination["page"] == 1
        assert pagination["per_page"] == 10
        assert pagination["total"] == 15
        assert pagination["total_pages"] == 2

    def cleanup(self):
        import gitlab_queue.api.routes as routes_module

        routes_module.UnitOfWork = self._original_uow
