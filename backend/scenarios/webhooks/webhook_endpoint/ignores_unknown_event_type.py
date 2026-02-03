"""Test that POST /webhooks/gitlab ignores unknown event types."""

from __future__ import annotations

import vedro
from scenarios.contexts.api_helpers import created_test_app
from scenarios.schemas.status_code import OkStatusSchema
from starlette.testclient import TestClient


class Scenario(vedro.Scenario):
    subject = "webhook endpoint ignores unknown event type"

    def given_app(self):
        self.app, self.state = created_test_app()
        self.webhook_secret = self.state.settings.webhook_secret.get_secret_value()
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.payload = {
            "object_kind": "tag_push",
            "project": {"id": self.state.settings.gitlab_project_id},
            "ref": "refs/tags/v1.0.0",
        }

    def when_webhook_is_called_with_unknown_event(self):
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
        assert data["reason"] == "unknown_event_type"
