"""Test that /auth/me rejects requests without token."""

from __future__ import annotations

import vedro
from scenarios.contexts.api_helpers import (
    created_test_app,
)
from scenarios.schemas.status_code import UnauthorizedStatusSchema
from starlette.testclient import TestClient


class Scenario(vedro.Scenario):
    subject = "try to get current user without authorization header"

    def given_app(self):
        self.app, self.state = created_test_app()
        self.client = TestClient(self.app)

    def when_me_endpoint_is_called_without_token(self):
        self.response = self.client.get("/auth/me")

    def then_it_should_return_401(self):
        assert self.response.status_code == UnauthorizedStatusSchema
        data = self.response.json()
        assert "authorization" in data["detail"].lower() or "missing" in data["detail"].lower()
