"""Test that /auth/login returns 503 when OAuth is not configured."""

from __future__ import annotations

import vedro
from scenarios.contexts.api_helpers import (
    create_mock_settings,
    created_test_app,
)
from scenarios.schemas.status_code import ServiceUnavailableStatusSchema
from starlette.testclient import TestClient


class Scenario(vedro.Scenario):
    subject = "try to login when oauth is not configured"

    def given_app_without_oauth(self):
        settings = create_mock_settings(
            oauth_client_id=None,
            oauth_client_secret=None,
        )
        self.app, self.state = created_test_app(settings=settings)
        self.client = TestClient(self.app)

    def when_login_endpoint_is_called(self):
        self.response = self.client.get("/auth/login")

    def then_it_should_return_503(self):
        assert self.response.status_code == ServiceUnavailableStatusSchema
        data = self.response.json()
        assert "not configured" in data["detail"].lower()
