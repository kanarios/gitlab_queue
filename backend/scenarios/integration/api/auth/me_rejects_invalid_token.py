"""Test that /auth/me rejects invalid tokens."""

from __future__ import annotations

import vedro
from scenarios.contexts.api_helpers import (
    create_invalid_jwt,
    created_test_app,
)
from scenarios.schemas.status_code import UnauthorizedStatusSchema
from starlette.testclient import TestClient


class Scenario(vedro.Scenario):
    subject = "try to get current user with invalid token"

    def given_app_with_invalid_token(self):
        self.app, self.state = created_test_app()
        self.client = TestClient(self.app)
        self.headers = {"Authorization": f"Bearer {create_invalid_jwt()}"}

    def when_me_endpoint_is_called(self):
        self.response = self.client.get("/auth/me", headers=self.headers)

    def then_it_should_return_401(self):
        assert self.response.status_code == UnauthorizedStatusSchema
        data = self.response.json()
        assert "invalid" in data["detail"].lower() or "token" in data["detail"].lower()
