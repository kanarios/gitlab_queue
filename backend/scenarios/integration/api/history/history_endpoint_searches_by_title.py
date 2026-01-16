"""Test that /api/history searches by title."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import vedro
from scenarios.contexts.api_helpers import (
    create_test_queue_item,
    created_test_app,
    created_test_jwt,
)
from scenarios.schemas.status_code import OkStatusSchema
from starlette.testclient import TestClient

from ._helpers import _queue_item_to_history_model


class Scenario(vedro.Scenario):
    subject = "history endpoint searches by title"

    def given_app_with_searchable_history(self):
        # Create items with specific titles
        item1 = create_test_queue_item(mr_iid=100, title="Fix login bug")
        item2 = create_test_queue_item(mr_iid=101, title="Add new feature")

        mock_result = MagicMock()
        mock_result.items = [
            _queue_item_to_history_model(item1),
            _queue_item_to_history_model(item2),
        ]
        mock_result.page = 1
        mock_result.per_page = 20
        mock_result.total = 2
        mock_result.total_pages = 1

        mock_uow = AsyncMock()
        mock_uow.history = MagicMock()
        mock_uow.history.get_history = AsyncMock(return_value=mock_result)
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

    def when_history_is_searched(self):
        self.response = self.client.get(
            "/api/history?search=login",
            headers=self.headers,
        )

    def then_it_should_filter_results(self):
        assert self.response.status_code == OkStatusSchema
        data = self.response.json()
        # Search filter is applied in-memory, so check results
        for item in data["items"]:
            # Either title, author_name, or author_username should contain search term
            title_match = "login" in item.get("title", "").lower()
            author_name_match = "login" in item.get("author", {}).get("name", "").lower()
            author_username_match = "login" in item.get("author", {}).get("username", "").lower()
            iid_match = str(item.get("mr_iid", "")) == "login"
            assert title_match or author_name_match or author_username_match or iid_match

    def cleanup(self):
        import gitlab_queue.api.routes as routes_module

        routes_module.UnitOfWork = self._original_uow
