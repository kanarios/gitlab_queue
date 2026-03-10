"""Test that /api/config requires authentication."""

from __future__ import annotations

import vedro
from scenarios.contexts.api_helpers import created_test_app
from scenarios.schemas.status_code import UnauthorizedStatusSchema
from starlette.testclient import TestClient


class Scenario(vedro.Scenario):
    subject = "config endpoint requires authentication"

    def given_app(self):
        self.app, self.state = created_test_app()
        self.client = TestClient(self.app, raise_server_exceptions=False)

    def when_config_is_requested_without_token(self):
        self.response = self.client.get("/api/config")

    def then_it_should_return_401(self):
        assert self.response.status_code == UnauthorizedStatusSchema
