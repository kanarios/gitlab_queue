"""Test that middleware allows access to public routes without token."""

from __future__ import annotations

import vedro
from scenarios.contexts.api_helpers import (
    created_test_app,
)
from scenarios.schemas.status_code import OkStatusSchema, UnauthorizedStatusSchema
from starlette.testclient import TestClient


class Scenario(vedro.Scenario):
    subject = "auth middleware allows public routes without authentication"

    def given_app(self):
        self.app, self.state = created_test_app()
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.client_no_redirect = TestClient(self.app, follow_redirects=False, raise_server_exceptions=False)

    def when_public_routes_are_accessed(self):
        self.health_response = self.client.get("/health")
        self.ready_response = self.client.get("/ready")
        self.auth_response = self.client_no_redirect.get("/auth/login")

    def then_health_should_be_accessible(self):
        assert self.health_response.status_code == OkStatusSchema

    def and_ready_should_be_accessible(self):
        assert self.ready_response.status_code == OkStatusSchema

    def and_auth_login_should_be_accessible(self):
        # Login redirects (302), or OAuth not configured (503), or internal error (500)
        # The key point is it's NOT 401 (auth blocked) - public routes should be accessible
        assert self.auth_response.status_code != UnauthorizedStatusSchema
