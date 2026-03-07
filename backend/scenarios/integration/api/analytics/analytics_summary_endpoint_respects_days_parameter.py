"""Test that /api/analytics/summary respects days parameter."""

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
    subject = "analytics summary endpoint respects days parameter"

    def given_app(self):
        self.app, self.state = created_test_app()
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.token = created_test_jwt(self.state.settings)
        self.headers = {"Authorization": f"Bearer {self.token}"}

        history_repo = FakeHistoryRepo(
            stats_for_period_result=HistoryStatsResult(
                total_processed=50,
                success_count=45,
                avg_wait_time_seconds=200,
                avg_processing_time_seconds=400,
            ),
        )
        uow = FakeUnitOfWork(history=history_repo)

        self.state.uow_factory = lambda db: uow

    def when_summary_is_called_with_days(self):
        self.response = self.client.get(
            "/api/analytics/summary?days=30",
            headers=self.headers,
        )

    def then_it_should_use_custom_days(self):
        assert self.response.status_code == OkStatusSchema
        data = self.response.json()
        assert data["period_days"] == 30
