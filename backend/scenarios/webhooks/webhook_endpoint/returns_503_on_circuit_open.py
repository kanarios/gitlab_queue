"""Test that POST /webhooks/gitlab returns 503 when GitLab circuit breaker is open."""

from __future__ import annotations

import vedro
from scenarios.contexts.api_helpers import created_test_app
from scenarios.schemas.status_code import ServiceUnavailableStatusSchema
from starlette.testclient import TestClient

from gitlab_queue.clients.gitlab import GitLabCircuitOpenError

from ._helpers import create_mr_webhook_payload


class Scenario(vedro.Scenario):
    subject = "webhook endpoint returns 503 when circuit breaker is open"

    def given_app_with_circuit_open(self):
        self.app, self.state = created_test_app()

        async def raise_circuit_open(state, event):
            raise GitLabCircuitOpenError(retry_after=30.0)

        self.state.event_router = raise_circuit_open
        self.webhook_secret = self.state.settings.webhook_secret.get_secret_value()
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.payload = create_mr_webhook_payload(
            project_id=self.state.settings.gitlab_project_id,
        )

    def when_webhook_is_called_and_circuit_is_open(self):
        self.response = self.client.post(
            "/webhooks/gitlab",
            json=self.payload,
            headers={"X-Gitlab-Token": self.webhook_secret},
        )

    def then_it_should_return_503(self):
        assert self.response.status_code == ServiceUnavailableStatusSchema

    def and_it_should_include_retry_after_header(self):
        assert "Retry-After" in self.response.headers
        assert self.response.headers["Retry-After"] == "30"

    def and_body_should_indicate_service_unavailable(self):
        data = self.response.json()
        assert data["status"] == "service_unavailable"
        assert data["retry_after"] == 30
