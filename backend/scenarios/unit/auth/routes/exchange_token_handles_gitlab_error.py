"""Test that POST /auth/token handles GitLab token exchange error."""

from __future__ import annotations

import secrets

import vedro
from starlette.testclient import TestClient

from scenarios.contexts.api_helpers import created_test_app

from ._helpers import create_oauth_transport


class Scenario(vedro.Scenario):
    subject = "exchange token handles GitLab error gracefully"

    def given_app_with_failing_gitlab(self):
        self.app, self.state = created_test_app()
        self.state.oauth_transport = create_oauth_transport(
            token_status=400,
            token_response_json={"error": "invalid_grant"},
        )
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.oauth_state = secrets.token_urlsafe(32)

    def when_token_exchange_fails(self):
        self.response = self.client.post(
            "/auth/token",
            params={
                "code": "invalid-code",
                "state": self.oauth_state,
            },
            cookies={"oauth_state": self.oauth_state},
        )

    def then_it_should_return_error_status(self):
        assert self.response.status_code == 502

    def and_detail_should_indicate_failure(self):
        data = self.response.json()
        assert "failed" in data["detail"].lower() or "token" in data["detail"].lower()
