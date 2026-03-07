"""Test that /api/history returns paginated results."""

from __future__ import annotations

import vedro
from scenarios.contexts.api_helpers import (
    create_test_history_items,
    created_test_app,
    created_test_jwt,
)
from scenarios.fakes import FakeHistoryRepo, FakeUnitOfWork, PaginatedHistoryResult
from scenarios.schemas.status_code import OkStatusSchema
from starlette.testclient import TestClient

from ._helpers import _queue_item_to_history_model

# Note: Starlette's BaseHTTPMiddleware has known issues with async context
# handling when combined with TestClient. Using raise_server_exceptions=False
# to work around this issue for authenticated endpoints.


class Scenario(vedro.Scenario):
    subject = "history endpoint returns paginated results"

    def given_app_with_history_data(self):
        history_items = create_test_history_items(count=15)
        self.first_item = history_items[0]
        history_repo = FakeHistoryRepo(
            get_history_result=PaginatedHistoryResult(
                items=[_queue_item_to_history_model(item) for item in history_items[:10]],
                page=1,
                per_page=10,
                total=15,
                total_pages=2,
            ),
        )
        uow = FakeUnitOfWork(history=history_repo)

        # Create app with uow_factory DI
        self.app, self.state = created_test_app()
        self.state.uow_factory = lambda db: uow
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.token = created_test_jwt(self.state.settings)
        self.headers = {"Authorization": f"Bearer {self.token}"}

    def when_history_endpoint_is_called(self):
        self.response = self.client.get(
            "/api/history?page=1&per_page=10",
            headers=self.headers,
        )

    def then_it_should_return_ok(self):
        assert self.response.status_code == OkStatusSchema

    def and_it_should_return_exactly_10_items(self):
        data = self.response.json()
        assert len(data["items"]) == 10

    def and_first_item_should_match(self):
        data = self.response.json()
        assert data["items"][0]["mr_iid"] == self.first_item.mr_iid

    def and_pagination_should_be_correct(self):
        pagination = self.response.json()["pagination"]
        assert pagination["page"] == 1
        assert pagination["per_page"] == 10
        assert pagination["total"] == 15
        assert pagination["total_pages"] == 2
