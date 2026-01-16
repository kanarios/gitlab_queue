"""Test that /auth/me rejects expired tokens."""

from __future__ import annotations

import vedro
from scenarios.contexts.api_helpers import (
    create_expired_jwt,
    created_test_app,
)
from scenarios.schemas.status_code import UnauthorizedStatusSchema
from starlette.testclient import TestClient


class Scenario(vedro.Scenario):
    subject = "try to get current user with expired token"

    def given_app_with_expired_token(self):
        self.app, self.state = created_test_app()
        self.client = TestClient(self.app)
        self.token = create_expired_jwt(self.state.settings)
        self.headers = {"Authorization": f"Bearer {self.token}"}

    def when_me_endpoint_is_called(self):
        self.response = self.client.get("/auth/me", headers=self.headers)

    def then_it_should_return_401(self):
        assert self.response.status_code == UnauthorizedStatusSchema
        data = self.response.json()
        assert "expired" in data["detail"].lower()
