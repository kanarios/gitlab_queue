"""Scenario: health endpoint returns 200 when process is alive."""

import vedro
from fastapi.testclient import TestClient
from scenarios.schemas.status_code import OkStatusSchema

from gitlab_queue.webhooks.router import create_webhook_app

from ._helpers import create_webhook_state


class Scenario(vedro.Scenario):
    subject = "health endpoint returns 200 when process is alive"

    def given_webhook_app(self):
        state = create_webhook_state()
        self.app = create_webhook_app(state)
        self.client = TestClient(self.app)

    def when_health_endpoint_is_called(self):
        self.response = self.client.get("/health")

    def then_it_should_return_200_with_healthy_status(self):
        assert self.response.status_code == OkStatusSchema
        data = self.response.json()
        assert data["status"] == "healthy"
        assert "mode" in data
        assert "components" in data
