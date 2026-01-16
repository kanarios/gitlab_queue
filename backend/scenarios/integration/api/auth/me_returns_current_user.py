"""Test that /auth/me returns current user info with valid token."""

from __future__ import annotations

import vedro
from scenarios.contexts.api_helpers import (
    created_test_app,
    created_test_jwt,
)
from scenarios.schemas.status_code import OkStatusSchema
from starlette.testclient import TestClient


class Scenario(vedro.Scenario):
    subject = "me endpoint returns current user information with valid token"

    def given_app_with_valid_token(self):
        self.app, self.state = created_test_app()
        self.client = TestClient(self.app)
        self.token = created_test_jwt(
            self.state.settings,
            user_id=12345,
            username="testuser",
            name="Test User",
            email="test@example.com",
        )
        self.headers = {"Authorization": f"Bearer {self.token}"}

    def when_me_endpoint_is_called(self):
        self.response = self.client.get("/auth/me", headers=self.headers)

    def then_it_should_return_user_info(self):
        assert self.response.status_code == OkStatusSchema
        data = self.response.json()
        assert data["id"] == "12345"
        assert data["username"] == "testuser"
        assert data["name"] == "Test User"
        assert data["email"] == "test@example.com"
