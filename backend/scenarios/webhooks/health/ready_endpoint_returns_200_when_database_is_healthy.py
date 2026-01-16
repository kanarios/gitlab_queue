"""Scenario: ready endpoint returns 200 when database is healthy."""

import vedro
from fastapi.testclient import TestClient
from scenarios.schemas.status_code import OkStatusSchema

from gitlab_queue.webhooks.router import create_webhook_app

from ._helpers import create_webhook_state


class Scenario(vedro.Scenario):
    subject = "ready endpoint returns 200 when database is healthy"

    def given_webhook_app_with_healthy_db(self):
        state = create_webhook_state(db_connected=True)
        self.app = create_webhook_app(state)
        self.client = TestClient(self.app)

    def when_ready_endpoint_is_called(self):
        self.response = self.client.get("/ready")

    def then_it_should_return_200_with_healthy_database(self):
        assert self.response.status_code == OkStatusSchema
        data = self.response.json()
        assert data["status"] == "healthy"
        assert data["database"]["connected"] is True
