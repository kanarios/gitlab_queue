"""Test that /api/analytics/outcomes returns outcome breakdown."""

from __future__ import annotations

import vedro
from scenarios.contexts.api_helpers import (
    created_test_app,
    created_test_jwt,
)
from scenarios.fakes import FakeHistoryRepo, FakeUnitOfWork, HistoryStatsResult
from scenarios.schemas.status_code import OkStatusSchema
from starlette.testclient import TestClient


class Scenario(vedro.Scenario):
    subject = "analytics outcomes endpoint returns outcome breakdown"

    def given_app_with_outcomes_data(self):
        self.app, self.state = created_test_app()
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.token = created_test_jwt(self.state.settings)
        self.headers = {"Authorization": f"Bearer {self.token}"}

        history_repo = FakeHistoryRepo(
            stats_for_period_result=HistoryStatsResult(
                total_processed=100,
                success_count=80,
                failed_count=10,
                conflict_count=7,
                timeout_count=3,
            ),
        )
        uow = FakeUnitOfWork(history=history_repo)

        self.state.uow_factory = lambda db: uow

    def when_outcomes_endpoint_is_called(self):
        self.response = self.client.get(
            "/api/analytics/outcomes",
            headers=self.headers,
        )

    def then_it_should_return_breakdown(self):
        assert self.response.status_code == OkStatusSchema
        data = self.response.json()

        assert "outcomes" in data
        assert "total" in data
        assert "period_days" in data

        # Verify outcome structure
        outcomes = data["outcomes"]
        assert len(outcomes) > 0

        for outcome in outcomes:
            assert "name" in outcome
            assert "count" in outcome
            assert "percentage" in outcome
