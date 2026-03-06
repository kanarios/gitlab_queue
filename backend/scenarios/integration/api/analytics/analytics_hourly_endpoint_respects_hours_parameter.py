"""Test that /api/analytics/hourly respects hours parameter."""

from __future__ import annotations

import vedro
from scenarios.contexts.api_helpers import (
    created_test_app,
    created_test_jwt,
)
from scenarios.fakes import FakeAnalyticsRepo, FakeUnitOfWork
from scenarios.schemas.status_code import OkStatusSchema
from starlette.testclient import TestClient


class Scenario(vedro.Scenario):
    subject = "analytics hourly endpoint respects hours parameter"

    def given_app(self):
        self.app, self.state = created_test_app()
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.token = created_test_jwt(self.state.settings)
        self.headers = {"Authorization": f"Bearer {self.token}"}

        analytics_repo = FakeAnalyticsRepo()
        uow = FakeUnitOfWork(analytics=analytics_repo)

        self.state.uow_factory = lambda db: uow

    def when_hourly_is_called_with_hours(self):
        self.response = self.client.get(
            "/api/analytics/hourly?hours=48",
            headers=self.headers,
        )

    def then_it_should_return_custom_hours(self):
        assert self.response.status_code == OkStatusSchema
        data = self.response.json()
        assert data["hours"] == 48
