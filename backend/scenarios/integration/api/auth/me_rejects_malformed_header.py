"""Test that /auth/me rejects malformed Authorization header."""

from __future__ import annotations

import vedro
from scenarios.contexts.api_helpers import (
    created_test_app,
)
from scenarios.schemas.status_code import UnauthorizedStatusSchema
from starlette.testclient import TestClient


class Scenario(vedro.Scenario):
    subject = "try to get current user with malformed authorization header"

    def given_app_with_malformed_header(self):
        self.app, self.state = created_test_app()
        self.client = TestClient(self.app)
        self.headers = {"Authorization": "InvalidFormat token123"}

    def when_me_endpoint_is_called(self):
        self.response = self.client.get("/auth/me", headers=self.headers)

    def then_it_should_return_401(self):
        assert self.response.status_code == UnauthorizedStatusSchema
        data = self.response.json()
        assert "invalid" in data["detail"].lower() or "format" in data["detail"].lower()
