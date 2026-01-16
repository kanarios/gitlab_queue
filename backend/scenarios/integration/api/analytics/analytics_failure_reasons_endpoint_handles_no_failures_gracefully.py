"""Test that /api/analytics/failure-reasons handles no failures gracefully."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import vedro
from scenarios.contexts.api_helpers import (
    created_test_app,
    created_test_jwt,
)
from scenarios.library import QueueState
from scenarios.schemas.status_code import OkStatusSchema
from starlette.testclient import TestClient


class Scenario(vedro.Scenario):
    subject = "analytics failure-reasons endpoint handles no failures gracefully"

    def given_app_with_no_failures(self):
        self.app, self.state = created_test_app()
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.token = created_test_jwt(self.state.settings)
        self.headers = {"Authorization": f"Bearer {self.token}"}

        # All items are merged (no failures)
        merged_item = MagicMock()
        merged_item.status = QueueState.MERGED
        merged_item.failure_reason = None

        mock_result = MagicMock()
        mock_result.items = [merged_item]
        mock_result.page = 1
        mock_result.per_page = 1000
        mock_result.total = 1
        mock_result.total_pages = 1

        mock_uow = AsyncMock()
        mock_uow.history = AsyncMock()
        mock_uow.history.get_history = AsyncMock(return_value=mock_result)
        mock_uow.__aenter__ = AsyncMock(return_value=mock_uow)
        mock_uow.__aexit__ = AsyncMock(return_value=None)

        import gitlab_queue.api.routes as routes_module

        self._original_uow = routes_module.UnitOfWork
        routes_module.UnitOfWork = MagicMock(return_value=mock_uow)

    def when_failure_reasons_endpoint_is_called(self):
        self.response = self.client.get(
            "/api/analytics/failure-reasons",
            headers=self.headers,
        )

    def then_it_should_return_empty_reasons(self):
        assert self.response.status_code == OkStatusSchema
        data = self.response.json()

        assert "reasons" in data
        assert "total_failures" in data
        assert data["total_failures"] == 0
        assert len(data["reasons"]) == 0

    def cleanup(self):
        import gitlab_queue.api.routes as routes_module

        routes_module.UnitOfWork = self._original_uow
