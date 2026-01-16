"""Test that /api/analytics/hourly validates hours parameter bounds."""

from __future__ import annotations

import vedro
from scenarios.contexts.api_helpers import (
    created_test_app,
    created_test_jwt,
)
from scenarios.schemas.status_code import UnprocessableEntityStatusSchema
from starlette.testclient import TestClient


class Scenario(vedro.Scenario):
    subject = "analytics hourly endpoint validates hours parameter bounds"

    def given_app(self):
        self.app, self.state = created_test_app()
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.token = created_test_jwt(self.state.settings)
        self.headers = {"Authorization": f"Bearer {self.token}"}

    def when_hourly_is_called_with_invalid_hours(self):
        # hours < 1 should fail
        self.response_too_low = self.client.get(
            "/api/analytics/hourly?hours=0",
            headers=self.headers,
        )
        # hours > 168 (7 days) should fail
        self.response_too_high = self.client.get(
            "/api/analytics/hourly?hours=169",
            headers=self.headers,
        )

    def then_invalid_hours_should_return_422(self):
        assert self.response_too_low.status_code == UnprocessableEntityStatusSchema
        assert self.response_too_high.status_code == UnprocessableEntityStatusSchema
