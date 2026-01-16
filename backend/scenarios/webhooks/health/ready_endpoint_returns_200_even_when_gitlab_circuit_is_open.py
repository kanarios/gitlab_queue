"""Scenario: ready endpoint returns 200 even when GitLab circuit is open."""

import vedro
from fastapi.testclient import TestClient
from scenarios.schemas.status_code import OkStatusSchema

from gitlab_queue.utils.circuit_breaker import CircuitState
from gitlab_queue.webhooks.router import create_webhook_app

from ._helpers import create_webhook_state


class Scenario(vedro.Scenario):
    subject = "ready endpoint returns 200 even when GitLab circuit is open"

    def given_webhook_app_with_open_circuit(self):
        state = create_webhook_state(
            db_connected=True,
            gitlab_circuit_state=CircuitState.OPEN,
        )
        self.app = create_webhook_app(state)
        self.client = TestClient(self.app)

    def when_ready_endpoint_is_called(self):
        self.response = self.client.get("/ready")

    def then_it_should_return_200_because_events_can_be_queued(self):
        # GitLab being down doesn't affect readiness - events get queued
        assert self.response.status_code == OkStatusSchema
        data = self.response.json()
        assert data["status"] == "healthy"
        assert data["database"]["connected"] is True
        # GitLab status should be reported but not affect readiness
        assert data["gitlab"]["status"] == "unhealthy"
        assert data["gitlab"]["circuit_state"] == "open"
