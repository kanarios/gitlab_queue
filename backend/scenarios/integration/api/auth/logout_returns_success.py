"""Test that /auth/logout returns success (stateless logout)."""

from __future__ import annotations

import vedro
from scenarios.contexts.api_helpers import (
    created_test_app,
)
from scenarios.schemas.status_code import OkStatusSchema
from starlette.testclient import TestClient


class Scenario(vedro.Scenario):
    subject = "logout endpoint returns success status"

    def given_app(self):
        self.app, self.state = created_test_app()
        self.client = TestClient(self.app)

    def when_logout_endpoint_is_called(self):
        self.response = self.client.post("/auth/logout")

    def then_it_should_return_success(self):
        assert self.response.status_code == OkStatusSchema
        data = self.response.json()
        assert data["status"] == "logged_out"
