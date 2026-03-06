"""Test that DELETE /api/dlq/{entry_id} deletes the entry successfully."""

from __future__ import annotations

import vedro
from scenarios.contexts.api_helpers import created_test_app, created_test_jwt
from scenarios.schemas.status_code import OkStatusSchema
from starlette.testclient import TestClient


class Scenario(vedro.Scenario):
    subject = "delete DLQ entry succeeds"

    def given_app_with_deletable_dlq_entry(self):
        self.app, self.state = created_test_app()
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.token = created_test_jwt(self.state.settings)
        self.headers = {"Authorization": f"Bearer {self.token}"}

    def when_dlq_entry_is_deleted(self):
        self.response = self.client.delete("/api/dlq/1", headers=self.headers)

    def then_it_should_return_200(self):
        assert self.response.status_code == OkStatusSchema

    def and_status_should_be_deleted(self):
        data = self.response.json()
        assert data["status"] == "deleted"
        assert data["entry_id"] == "1"
