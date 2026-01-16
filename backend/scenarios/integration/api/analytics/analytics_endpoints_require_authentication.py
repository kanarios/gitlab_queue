"""Test that /api/analytics requires authentication."""

from __future__ import annotations

import vedro
from scenarios.contexts.api_helpers import (
    created_test_app,
)
from scenarios.schemas.status_code import UnauthorizedStatusSchema
from starlette.testclient import TestClient


class Scenario(vedro.Scenario):
    subject = "analytics endpoints require authentication"

    def given_app(self):
        self.app, self.state = created_test_app()
        self.client = TestClient(self.app, raise_server_exceptions=False)

    def when_analytics_is_called_without_token(self):
        self.summary_response = self.client.get("/api/analytics/summary")
        self.hourly_response = self.client.get("/api/analytics/hourly")
        self.outcomes_response = self.client.get("/api/analytics/outcomes")

    def then_summary_should_return_401(self):
        assert self.summary_response.status_code == UnauthorizedStatusSchema

    def and_hourly_should_return_401(self):
        assert self.hourly_response.status_code == UnauthorizedStatusSchema

    def and_outcomes_should_return_401(self):
        assert self.outcomes_response.status_code == UnauthorizedStatusSchema
