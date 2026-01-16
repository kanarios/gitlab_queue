"""Test that /api/history filters by status."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import vedro
from scenarios.contexts.api_helpers import (
    create_test_queue_item,
    created_test_app,
    created_test_jwt,
)
from scenarios.library import QueueState
from scenarios.schemas.status_code import OkStatusSchema
from starlette.testclient import TestClient

from ._helpers import _queue_item_to_history_model


class Scenario(vedro.Scenario):
    subject = "history endpoint filters by status parameter"

    def given_app_with_mock_history(self):
        # Create mock history with specific status
        merged_item = create_test_queue_item(mr_iid=100, state=QueueState.MERGED)
        mock_result = MagicMock()
        mock_result.items = [_queue_item_to_history_model(merged_item)]
        mock_result.page = 1
        mock_result.per_page = 20
        mock_result.total = 1
        mock_result.total_pages = 1

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

    def when_history_is_called_with_status_filter(self):
        self.response = self.client.get(
            "/api/history?status=merged",
            headers=self.headers,
        )

    def then_it_should_pass_status_to_repository(self):
        assert self.response.status_code == OkStatusSchema
        # Verify the status filter was passed to get_history
        call_args = self._mock_uow.history.get_history.call_args
        assert call_args is not None
        assert call_args.kwargs.get("status_filter") == "merged"

    def cleanup(self):
        import gitlab_queue.api.routes as routes_module

        routes_module.UnitOfWork = self._original_uow
