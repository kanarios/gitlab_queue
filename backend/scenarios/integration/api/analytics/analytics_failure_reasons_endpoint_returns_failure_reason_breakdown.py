"""Test that /api/analytics/failure-reasons returns failure reasons."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import vedro
from scenarios.library import QueueState
from scenarios.contexts.api_helpers import (
    created_test_app,
    created_test_jwt,
)
from scenarios.schemas.status_code import OkStatusSchema
from starlette.testclient import TestClient


class Scenario(vedro.Scenario):
    subject = "analytics failure-reasons endpoint returns failure reason breakdown"

    def given_app_with_failure_data(self):
        self.app, self.state = created_test_app()
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.token = created_test_jwt(self.state.settings)
        self.headers = {"Authorization": f"Bearer {self.token}"}

        # Create mock history items with failures
        failed_item1 = MagicMock()
        failed_item1.status = QueueState.FAILED
        failed_item1.failure_reason = "Pipeline failed: test failure"

        failed_item2 = MagicMock()
        failed_item2.status = QueueState.CONFLICT
        failed_item2.failure_reason = "Merge conflict in src/main.py"

        merged_item = MagicMock()
        merged_item.status = QueueState.MERGED
        merged_item.failure_reason = None

        mock_result = MagicMock()
        mock_result.items = [failed_item1, failed_item2, merged_item]
        mock_result.page = 1
        mock_result.per_page = 1000
        mock_result.total = 3
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

    def then_it_should_return_reasons(self):
        assert self.response.status_code == OkStatusSchema
        data = self.response.json()

        assert "reasons" in data
        assert "total_failures" in data
        assert "period_days" in data

        # Should have 2 failures
        assert data["total_failures"] == 2

        # Verify reason structure
        for reason in data["reasons"]:
            assert "reason" in reason
            assert "count" in reason
            assert "percentage" in reason

    def cleanup(self):
        import gitlab_queue.api.routes as routes_module

        routes_module.UnitOfWork = self._original_uow
