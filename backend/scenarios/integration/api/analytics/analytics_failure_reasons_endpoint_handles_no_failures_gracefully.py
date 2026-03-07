"""Test that /api/analytics/failure-reasons handles no failures gracefully."""

from __future__ import annotations

import vedro
from scenarios.contexts.api_helpers import (
    created_test_app,
    created_test_jwt,
)
from scenarios.fakes import (
    FakeHistoryRepo,
    FakeUnitOfWork,
    HistoryItemModel,
    PaginatedHistoryResult,
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

        merged_item = HistoryItemModel(
            status=QueueState.MERGED,
            failure_reason=None,
        )

        history_repo = FakeHistoryRepo(
            get_history_result=PaginatedHistoryResult(
                items=[merged_item],
                page=1,
                per_page=1000,
                total=1,
                total_pages=1,
            ),
        )
        uow = FakeUnitOfWork(history=history_repo)

        self.state.uow_factory = lambda db: uow

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
