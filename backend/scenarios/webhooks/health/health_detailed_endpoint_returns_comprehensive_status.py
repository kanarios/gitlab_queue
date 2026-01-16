"""Scenario: health detailed endpoint returns comprehensive status."""

import vedro
from fastapi.testclient import TestClient
from scenarios.schemas.status_code import OkStatusSchema

from gitlab_queue.webhooks.router import create_webhook_app

from ._helpers import create_webhook_state


class Scenario(vedro.Scenario):
    subject = "health detailed endpoint returns comprehensive status"

    def given_webhook_app(self):
        state = create_webhook_state()
        self.app = create_webhook_app(state)
        self.client = TestClient(self.app)

    def when_health_detailed_endpoint_is_called(self):
        self.response = self.client.get("/health/detailed")

    def then_it_should_return_all_component_details(self):
        assert self.response.status_code == OkStatusSchema
        data = self.response.json()

        # Check all required fields are present
        assert "status" in data
        assert "mode" in data
        assert "database" in data
        assert "gitlab" in data
        assert "processor_running" in data
        assert "webhook_server_running" in data

        # Check database details
        assert "connected" in data["database"]
        assert "wal_mode_enabled" in data["database"]
        assert "foreign_keys_enabled" in data["database"]

        # Check GitLab details
        assert "status" in data["gitlab"]
        assert "circuit_breaker" in data["gitlab"]
        assert "rate_limit" in data["gitlab"]

        # Check circuit breaker details
        cb = data["gitlab"]["circuit_breaker"]
        assert "state" in cb
        assert "failure_count" in cb
        assert "failure_threshold" in cb

        # Check rate limit details
        rl = data["gitlab"]["rate_limit"]
        assert "limit" in rl
        assert "remaining" in rl
        assert "usage_ratio" in rl
