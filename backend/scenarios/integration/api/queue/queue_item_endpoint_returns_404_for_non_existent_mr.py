"""Test that /api/queue/{mr_iid} returns 404 for non-existent MR."""

from __future__ import annotations

from unittest.mock import AsyncMock

import vedro
from scenarios.contexts.api_helpers import (
    created_test_app,
    created_test_jwt,
)
from scenarios.schemas.status_code import NotFoundStatusSchema
from starlette.testclient import TestClient


class Scenario(vedro.Scenario):
    subject = "try to get queue item for non-existent mr"

    def given_app_with_no_item(self):
        self.app, self.state = created_test_app()
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.token = created_test_jwt(self.state.settings)
        self.headers = {"Authorization": f"Bearer {self.token}"}

        self.state.queue_manager.get_queue_item = AsyncMock(return_value=None)

    def when_nonexistent_item_is_requested(self):
        self.response = self.client.get("/api/queue/99999", headers=self.headers)

    def then_it_should_return_404(self):
        assert self.response.status_code == NotFoundStatusSchema
        data = self.response.json()
        assert "not found" in data["detail"].lower()
