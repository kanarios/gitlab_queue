"""Test that /api/history/{iid} returns a single MR."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import vedro
from scenarios.library import QueueState
from scenarios.contexts.api_helpers import (
    create_test_queue_item,
    created_test_app,
    created_test_jwt,
)
from scenarios.schemas.status_code import OkStatusSchema
from starlette.testclient import TestClient

from ._helpers import _queue_item_to_history_model


class Scenario(vedro.Scenario):
    subject = "history item endpoint returns single MR details"

    def given_app_with_history_item(self):
        # Create mock item
        item = create_test_queue_item(
            mr_iid=42,
            title="Test MR #42",
            state=QueueState.MERGED,
        )
        mock_model = _queue_item_to_history_model(item)

        mock_uow = AsyncMock()
        mock_uow.history = MagicMock()
        mock_uow.history.get_by_iid = AsyncMock(return_value=mock_model)
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

    def when_history_item_is_requested(self):
        self.response = self.client.get(
            "/api/history/42",
            headers=self.headers,
        )

    def then_it_should_return_item_details(self):
        assert self.response.status_code == OkStatusSchema
        data = self.response.json()
        assert data["mr_iid"] == 42
        assert data["title"] == "Test MR #42"
        assert data["status"] == "merged"

    def cleanup(self):
        import gitlab_queue.api.routes as routes_module

        routes_module.UnitOfWork = self._original_uow
