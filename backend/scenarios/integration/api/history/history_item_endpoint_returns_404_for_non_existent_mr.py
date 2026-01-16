"""Test that /api/history/{iid} returns 404 for non-existent MR."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import vedro
from scenarios.contexts.api_helpers import (
    created_test_app,
    created_test_jwt,
)
from scenarios.schemas.status_code import NotFoundStatusSchema
from starlette.testclient import TestClient


class Scenario(vedro.Scenario):
    subject = "try to get history item for non-existent mr"

    def given_app_with_empty_history(self):
        mock_uow = AsyncMock()
        mock_uow.history = MagicMock()
        mock_uow.history.get_by_iid = AsyncMock(return_value=None)
        mock_uow.__aenter__ = AsyncMock(return_value=mock_uow)
        mock_uow.__aexit__ = AsyncMock(return_value=None)

        import gitlab_queue.api.routes as routes_module

        self._original_uow = routes_module.UnitOfWork
        routes_module.UnitOfWork = MagicMock(return_value=mock_uow)

        # Create app AFTER patching
        self.app, self.state = created_test_app()
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.token = created_test_jwt(self.state.settings)
        self.headers = {"Authorization": f"Bearer {self.token}"}

    def when_nonexistent_item_is_requested(self):
        self.response = self.client.get(
            "/api/history/99999",
            headers=self.headers,
        )

    def then_it_should_return_404(self):
        assert self.response.status_code == NotFoundStatusSchema
        data = self.response.json()
        assert "not found" in data["detail"].lower()

    def cleanup(self):
        import gitlab_queue.api.routes as routes_module

        routes_module.UnitOfWork = self._original_uow
