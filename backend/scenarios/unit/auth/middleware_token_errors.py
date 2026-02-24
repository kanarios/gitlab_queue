"""Test error handling for invalid/expired tokens in auth middleware.

Covers middleware.py lines 167-172:
- TokenExpiredError returns 'Token has expired'
- InvalidTokenError returns 'Invalid token'
- Invalid Authorization header format returns error
"""

from __future__ import annotations

import vedro
from scenarios.contexts.api_helpers import (
    created_expired_jwt,
    created_invalid_jwt,
    created_test_app,
)
from starlette.testclient import TestClient


class Scenario(vedro.Scenario):
    subject = "middleware returns 401 for expired JWT token"

    def given_app_with_expired_token(self):
        self.app, self.state = created_test_app()
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.token = created_expired_jwt(self.state.settings)

    def when_protected_endpoint_is_called(self):
        self.response = self.client.get(
            "/health/detailed",
            headers={"Authorization": f"Bearer {self.token}"},
        )

    def then_status_code_is_401(self):
        assert self.response.status_code == 401

    def and_detail_mentions_expired(self):
        data = self.response.json()
        assert "expired" in data["detail"].lower()


class ScenarioInvalidToken(vedro.Scenario):
    subject = "middleware returns 401 for invalid JWT token"

    def given_app_with_invalid_token(self):
        self.app, self.state = created_test_app()
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.token = created_invalid_jwt()

    def when_protected_endpoint_is_called(self):
        self.response = self.client.get(
            "/health/detailed",
            headers={"Authorization": f"Bearer {self.token}"},
        )

    def then_status_code_is_401(self):
        assert self.response.status_code == 401

    def and_detail_mentions_invalid_token(self):
        data = self.response.json()
        assert "invalid" in data["detail"].lower()


class ScenarioMissingAuth(vedro.Scenario):
    subject = "middleware returns 401 for missing Authorization header"

    def given_app_with_no_auth_header(self):
        self.app, self.state = created_test_app()
        self.client = TestClient(self.app, raise_server_exceptions=False)

    def when_protected_endpoint_is_called_without_auth(self):
        self.response = self.client.get("/health/detailed")

    def then_status_code_is_401(self):
        assert self.response.status_code == 401

    def and_detail_mentions_missing_authorization(self):
        data = self.response.json()
        assert "authorization" in data["detail"].lower() or "missing" in data["detail"].lower()


class ScenarioMalformedAuth(vedro.Scenario):
    subject = "middleware returns 401 for malformed Authorization header"

    def given_app_with_malformed_auth_header(self):
        self.app, self.state = created_test_app()
        self.client = TestClient(self.app, raise_server_exceptions=False)

    def when_protected_endpoint_is_called_with_bad_format(self):
        self.response = self.client.get(
            "/health/detailed",
            headers={"Authorization": "NotBearer sometoken"},
        )

    def then_status_code_is_401(self):
        assert self.response.status_code == 401

    def and_detail_mentions_invalid_format(self):
        data = self.response.json()
        assert "invalid" in data["detail"].lower() or "format" in data["detail"].lower()
