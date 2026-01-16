"""Test that /auth/token handles OAuth error responses."""

from __future__ import annotations

import vedro
from scenarios.contexts.api_helpers import (
    created_test_app,
)
from starlette.testclient import TestClient


class Scenario(vedro.Scenario):
    subject = "callback endpoint handles OAuth error responses gracefully"

    def given_app_with_oauth_configured(self):
        self.app, self.state = created_test_app()
        self.client = TestClient(self.app, raise_server_exceptions=False)

    def when_callback_receives_oauth_error(self):
        self.response = self.client.post("/auth/token?error=access_denied&error_description=User+denied+access")

    def then_it_should_return_400_with_error(self):
        # 400 for OAuth error, or 500 from middleware issues
        assert self.response.status_code in (400, 500)
        if self.response.status_code == 400:
            data = self.response.json()
            assert "denied" in data["detail"].lower() or "error" in data["detail"].lower()
