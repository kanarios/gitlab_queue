"""Scenario: ready endpoint returns 503 when database is unhealthy."""

import vedro
from fastapi.testclient import TestClient
from scenarios.schemas.status_code import ServiceUnavailableStatusSchema

from gitlab_queue.webhooks.router import create_webhook_app

from ._helpers import create_webhook_state


class Scenario(vedro.Scenario):
    subject = "ready endpoint returns 503 when database is unhealthy"

    def given_webhook_app_with_unhealthy_db(self):
        state = create_webhook_state(db_connected=False)
        self.app = create_webhook_app(state)
        self.client = TestClient(self.app)

    def when_ready_endpoint_is_called(self):
        self.response = self.client.get("/ready")

    def then_it_should_return_503_with_error_reason(self):
        assert self.response.status_code == ServiceUnavailableStatusSchema
        data = self.response.json()
        assert data["status"] == "unhealthy"
        assert data["reason"] == "database_unavailable"
        assert data["database"]["connected"] is False
