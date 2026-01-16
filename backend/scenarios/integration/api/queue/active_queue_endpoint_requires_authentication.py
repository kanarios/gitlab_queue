"""Test that /api/queue/active requires authentication."""

from __future__ import annotations

import vedro
from scenarios.contexts.api_helpers import created_test_app
from scenarios.schemas.status_code import UnauthorizedStatusSchema
from starlette.testclient import TestClient


class Scenario(vedro.Scenario):
    subject = "active queue endpoint requires authentication"

    def given_app(self):
        self.app, self.state = created_test_app()
        self.client = TestClient(self.app, raise_server_exceptions=False)

    def when_active_queue_is_requested_without_token(self):
        self.response = self.client.get("/api/queue/active")

    def then_it_should_return_401(self):
        assert self.response.status_code == UnauthorizedStatusSchema
