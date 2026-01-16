"""Test that middleware allows authenticated requests to protected routes."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import vedro
from scenarios.contexts.api_helpers import (
    created_test_app,
    created_test_jwt,
)
from starlette.testclient import TestClient


class Scenario(vedro.Scenario):
    subject = "auth middleware allows authenticated requests to protected routes"

    def given_app_with_valid_token(self):
        self.app, self.state = created_test_app()
        self.client = TestClient(self.app)
        self.token = created_test_jwt(self.state.settings)
        self.headers = {"Authorization": f"Bearer {self.token}"}

        # Mock UnitOfWork to avoid database calls
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

    def when_protected_route_is_accessed_with_token(self):
        self.response = self.client.get("/api/history", headers=self.headers)

    def then_it_should_not_return_401(self):
        # Should not be 401 - might be 200 or another error depending on data
        assert self.response.status_code != 401

    def cleanup(self):
        import gitlab_queue.api.routes as routes_module

        routes_module.UnitOfWork = self._original_uow
