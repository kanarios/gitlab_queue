"""Test that GET /api/dlq/{entry_id} returns 404 when entry not found."""

from __future__ import annotations

import vedro
from scenarios.contexts.api_helpers import created_test_app, created_test_jwt
from scenarios.schemas.status_code import NotFoundStatusSchema
from starlette.testclient import TestClient

from gitlab_queue.webhooks.retry_manager import DLQItemNotFoundError


class Scenario(vedro.Scenario):
    subject = "get DLQ entry returns 404 when not found"

    def given_app_with_missing_dlq_entry(self):
        self.app, self.state = created_test_app()
        self.state.retry_manager.dlq_error = DLQItemNotFoundError(999)
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.token = created_test_jwt(self.state.settings)
        self.headers = {"Authorization": f"Bearer {self.token}"}

    def when_nonexistent_dlq_entry_is_requested(self):
        self.response = self.client.get("/api/dlq/999", headers=self.headers)

    def then_it_should_return_404(self):
        assert self.response.status_code == NotFoundStatusSchema
