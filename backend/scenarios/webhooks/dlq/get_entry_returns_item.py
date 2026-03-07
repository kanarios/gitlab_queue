"""Test that GET /api/dlq/{entry_id} returns the requested item."""

from __future__ import annotations

import vedro
from scenarios.contexts.api_helpers import created_test_app, created_test_jwt
from scenarios.schemas.status_code import OkStatusSchema
from starlette.testclient import TestClient

from ._helpers import create_test_dlq_item


class Scenario(vedro.Scenario):
    subject = "get DLQ entry returns item"

    def given_app_with_dlq_entry(self):
        self.app, self.state = created_test_app()
        self.item = create_test_dlq_item(entry_id=1, event_type="merge_request")
        self.state.retry_manager.dlq_entry = self.item
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.token = created_test_jwt(self.state.settings)
        self.headers = {"Authorization": f"Bearer {self.token}"}

    def when_dlq_entry_is_requested(self):
        self.response = self.client.get("/api/dlq/1", headers=self.headers)

    def then_it_should_return_200(self):
        assert self.response.status_code == OkStatusSchema

    def and_it_should_contain_item_data(self):
        data = self.response.json()
        assert data["id"] == 1
        assert data["event_type"] == "merge_request"
        assert data["attempt_count"] == 3
        assert data["last_error"] == "Final error"
