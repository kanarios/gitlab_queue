"""Test that POST /webhooks/gitlab ignores events for a different project."""

from __future__ import annotations

import vedro
from scenarios.contexts.api_helpers import created_test_app
from scenarios.schemas.status_code import OkStatusSchema
from starlette.testclient import TestClient

from ._helpers import create_mr_webhook_payload


class Scenario(vedro.Scenario):
    subject = "webhook endpoint ignores wrong project ID"

    def given_app(self):
        self.app, self.state = created_test_app()
        self.webhook_secret = self.state.settings.webhook_secret.get_secret_value()
        self.client = TestClient(self.app, raise_server_exceptions=False)
        # Use a different project_id than configured
        self.payload = create_mr_webhook_payload(project_id=999)

    def when_webhook_is_called_with_wrong_project(self):
        self.response = self.client.post(
            "/webhooks/gitlab",
            json=self.payload,
            headers={"X-Gitlab-Token": self.webhook_secret},
        )

    def then_it_should_return_200(self):
        assert self.response.status_code == OkStatusSchema

    def and_status_should_be_ignored(self):
        data = self.response.json()
        assert data["status"] == "ignored"
        assert data["reason"] == "project_id_mismatch"
