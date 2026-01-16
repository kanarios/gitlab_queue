"""Scenario: health endpoints include X-Request-Id header."""

import vedro
from fastapi.testclient import TestClient

from gitlab_queue.webhooks.router import create_webhook_app

from ._helpers import create_webhook_state


class Scenario(vedro.Scenario):
    subject = "health endpoints include X-Request-Id header"

    def given_webhook_app(self):
        state = create_webhook_state()
        self.app = create_webhook_app(state)
        self.client = TestClient(self.app)

    def when_health_endpoint_is_called(self):
        self.response = self.client.get("/health")

    def then_response_should_have_request_id_header(self):
        assert "x-request-id" in self.response.headers
        request_id = self.response.headers["x-request-id"]
        assert len(request_id) > 0
