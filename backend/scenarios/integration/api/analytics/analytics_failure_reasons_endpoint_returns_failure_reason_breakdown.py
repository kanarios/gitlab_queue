"""Test that /api/analytics/failure-reasons returns failure reasons."""

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
    subject = "analytics failure-reasons endpoint returns failure reason breakdown"

    def given_app_with_failure_data(self):
        self.app, self.state = created_test_app()
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.token = created_test_jwt(self.state.settings)
        self.headers = {"Authorization": f"Bearer {self.token}"}

        failed_item1 = HistoryItemModel(
            status=QueueState.FAILED,
            failure_reason="Pipeline failed: test failure",
        )
        failed_item2 = HistoryItemModel(
            status=QueueState.CONFLICT,
            failure_reason="Merge conflict in src/main.py",
        )
        merged_item = HistoryItemModel(
            status=QueueState.MERGED,
            failure_reason=None,
        )

        history_repo = FakeHistoryRepo(
            get_history_result=PaginatedHistoryResult(
                items=[failed_item1, failed_item2, merged_item],
                page=1,
                per_page=1000,
                total=3,
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

    def then_it_should_return_ok(self):
        assert self.response.status_code == OkStatusSchema

    def and_it_should_have_two_total_failures(self):
        data = self.response.json()
        assert data["total_failures"] == 2

    def and_it_should_contain_both_failure_reasons(self):
        reasons = self.response.json()["reasons"]
        reason_map = {r["reason"]: r["count"] for r in reasons}
        assert reason_map == {
            "Pipeline failed: test failure": 1,
            "Merge conflict in src/main.py": 1,
        }
