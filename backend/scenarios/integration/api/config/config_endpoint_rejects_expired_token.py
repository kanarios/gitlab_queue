"""Test that /api/config rejects expired token."""

from __future__ import annotations

import vedro
from scenarios.contexts.api_helpers import created_expired_jwt, created_test_app
from scenarios.schemas.status_code import UnauthorizedStatusSchema
from starlette.testclient import TestClient


class Scenario(vedro.Scenario):
    subject = "config endpoint rejects expired token"

    def given_app(self):
        self.app, self.state = created_test_app()
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.token = created_expired_jwt(self.state.settings)
        self.headers = {"Authorization": f"Bearer {self.token}"}

    def when_config_is_requested_with_expired_token(self):
        self.response = self.client.get("/api/config", headers=self.headers)

    def then_it_should_return_401(self):
        assert self.response.status_code == UnauthorizedStatusSchema
