"""Test that POST /api/dlq/{entry_id}/retry requeues the entry."""

from __future__ import annotations

from unittest.mock import AsyncMock

import vedro
from scenarios.contexts.api_helpers import created_test_app, created_test_jwt
from scenarios.schemas.status_code import OkStatusSchema
from starlette.testclient import TestClient


class Scenario(vedro.Scenario):
    subject = "retry DLQ entry requeues it successfully"

    def given_app_with_retryable_dlq_entry(self):
        self.app, self.state = created_test_app()
        self.state.retry_manager.retry_dlq_entry = AsyncMock(return_value=5)
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.token = created_test_jwt(self.state.settings)
        self.headers = {"Authorization": f"Bearer {self.token}"}

    def when_dlq_entry_is_retried(self):
        self.response = self.client.post("/api/dlq/1/retry", headers=self.headers)

    def then_it_should_return_200(self):
        assert self.response.status_code == OkStatusSchema

    def and_status_should_be_requeued(self):
        data = self.response.json()
        assert data["status"] == "requeued"
        assert data["retry_id"] == 5
        assert data["dlq_entry_id"] == 1
