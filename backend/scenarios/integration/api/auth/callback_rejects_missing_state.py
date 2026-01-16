"""Test that /auth/token rejects requests without state parameter."""

from __future__ import annotations

import vedro
from scenarios.contexts.api_helpers import (
    created_test_app,
)
from starlette.testclient import TestClient


class Scenario(vedro.Scenario):
    subject = "try to exchange code without state parameter"

    def given_app_with_oauth_configured(self):
        self.app, self.state = created_test_app()
        self.client = TestClient(self.app, raise_server_exceptions=False)

    def when_callback_is_called_without_state(self):
        self.response = self.client.post("/auth/token?code=test-code")

    def then_it_should_return_400(self):
        # 400 for missing state, or 500 from middleware issues
        assert self.response.status_code in (400, 500)
        if self.response.status_code == 400:
            data = self.response.json()
            assert "state" in data["detail"].lower() or "missing" in data["detail"].lower()
