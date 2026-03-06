"""Test that /api/queue/active returns empty list when queue is empty."""

from __future__ import annotations

import vedro
from scenarios.contexts.api_helpers import (
    created_test_app,
    created_test_jwt,
)
from scenarios.schemas.status_code import OkStatusSchema
from starlette.testclient import TestClient


class Scenario(vedro.Scenario):
    subject = "active queue endpoint returns empty list when queue is empty"

    def given_app_with_empty_queue(self):
        self.app, self.state = created_test_app()
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.token = created_test_jwt(self.state.settings)
        self.headers = {"Authorization": f"Bearer {self.token}"}

    def when_active_queue_is_requested(self):
        self.response = self.client.get("/api/queue/active", headers=self.headers)

    def then_it_should_return_empty_list(self):
        assert self.response.status_code == OkStatusSchema
        data = self.response.json()

        assert data["items"] == []
        assert data["count"] == 0
