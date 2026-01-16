"""Test that middleware blocks access to protected routes without token."""

from __future__ import annotations

import vedro
from scenarios.contexts.api_helpers import (
    created_test_app,
)
from scenarios.schemas.status_code import UnauthorizedStatusSchema
from starlette.testclient import TestClient


class Scenario(vedro.Scenario):
    subject = "try to access protected route without token"

    def given_app(self):
        self.app, self.state = created_test_app()
        self.client = TestClient(self.app)

    def when_protected_route_is_accessed(self):
        # /api/history is a protected route
        self.response = self.client.get("/api/history")

    def then_it_should_return_401(self):
        assert self.response.status_code == UnauthorizedStatusSchema
        assert "WWW-Authenticate" in self.response.headers
