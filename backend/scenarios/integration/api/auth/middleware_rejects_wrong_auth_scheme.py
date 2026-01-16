"""Test that middleware rejects non-Bearer auth schemes."""

from __future__ import annotations

import vedro
from scenarios.contexts.api_helpers import (
    created_test_app,
)
from scenarios.schemas.status_code import UnauthorizedStatusSchema
from starlette.testclient import TestClient


class Scenario(vedro.Scenario):
    subject = "try to access protected route with non-bearer auth scheme"

    def given_app_with_basic_auth(self):
        self.app, self.state = created_test_app()
        self.client = TestClient(self.app)
        self.headers = {"Authorization": "Basic dXNlcjpwYXNz"}

    def when_protected_route_is_accessed(self):
        self.response = self.client.get("/api/history", headers=self.headers)

    def then_it_should_return_401(self):
        assert self.response.status_code == UnauthorizedStatusSchema
        data = self.response.json()
        assert "bearer" in data["detail"].lower() or "format" in data["detail"].lower()
