"""Test that /api/history filters by status."""

from __future__ import annotations

import vedro
from scenarios.contexts.api_helpers import (
    create_test_queue_item,
    created_test_app,
    created_test_jwt,
)
from scenarios.fakes import (
    FakeHistoryRepo,
    FakeUnitOfWork,
    PaginatedHistoryResult,
)
from scenarios.library import QueueState
from scenarios.schemas.status_code import OkStatusSchema
from starlette.testclient import TestClient

from ._helpers import _queue_item_to_history_model


class Scenario(vedro.Scenario):
    subject = "history endpoint filters by status parameter"

    def given_app_with_mock_history(self):
        merged_item = create_test_queue_item(mr_iid=100, state=QueueState.MERGED)
        self._history_repo = FakeHistoryRepo(
            get_history_result=PaginatedHistoryResult(
                items=[_queue_item_to_history_model(merged_item)],
                page=1,
                per_page=20,
                total=1,
                total_pages=1,
            ),
        )
        uow = FakeUnitOfWork(history=self._history_repo)

        # Create app with uow_factory DI
        self.app, self.state = created_test_app()
        self.state.uow_factory = lambda db: uow
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.token = created_test_jwt(self.state.settings)
        self.headers = {"Authorization": f"Bearer {self.token}"}

    def when_history_is_called_with_status_filter(self):
        self.response = self.client.get(
            "/api/history?status=merged",
            headers=self.headers,
        )

    def then_it_should_return_ok(self):
        assert self.response.status_code == OkStatusSchema

    def and_it_should_pass_status_to_repository(self):
        assert len(self._history_repo.get_history_calls) == 1
        call_kwargs = self._history_repo.get_history_calls[0]
        assert call_kwargs.get("status_filter") == "merged"

    def and_response_should_contain_the_filtered_item(self):
        data = self.response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["mr_iid"] == 100
