"""Test that POST /webhooks/gitlab rejects a request without X-Gitlab-Token header."""

from __future__ import annotations

import vedro
from scenarios.contexts.api_helpers import created_test_app
from scenarios.schemas.status_code import UnprocessableEntityStatusSchema
from starlette.testclient import TestClient

from ._helpers import create_mr_webhook_payload


class Scenario(vedro.Scenario):
    subject = "webhook endpoint rejects missing token header"

    def given_app(self):
        self.app, self.state = created_test_app()
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.payload = create_mr_webhook_payload(
            project_id=self.state.settings.gitlab_project_id,
        )

    def when_webhook_is_called_without_token(self):
        self.response = self.client.post(
            "/webhooks/gitlab",
            json=self.payload,
        )

    def then_it_should_return_422(self):
        assert self.response.status_code == UnprocessableEntityStatusSchema
