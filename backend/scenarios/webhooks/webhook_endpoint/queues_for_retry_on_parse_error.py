"""Test that POST /webhooks/gitlab queues for retry when payload parsing fails."""

from __future__ import annotations

import vedro
from scenarios.contexts.api_helpers import created_test_app
from scenarios.schemas.status_code import OkStatusSchema
from starlette.testclient import TestClient


class Scenario(vedro.Scenario):
    subject = "webhook endpoint queues for retry on parse error"

    def given_app_with_valid_token(self):
        self.app, self.state = created_test_app()
        self.webhook_secret = self.state.settings.webhook_secret.get_secret_value()
        self.client = TestClient(self.app, raise_server_exceptions=False)
        # Payload has object_kind=merge_request but missing required fields
        # that will cause parse_webhook_event to raise ValueError/KeyError
        self.payload = {
            "object_kind": "merge_request",
            "project": {"id": self.state.settings.gitlab_project_id},
            # Missing object_attributes, user, labels, etc.
        }

    def when_webhook_is_called_with_bad_payload(self):
        self.response = self.client.post(
            "/webhooks/gitlab",
            json=self.payload,
            headers={"X-Gitlab-Token": self.webhook_secret},
        )

    def then_it_should_return_200(self):
        assert self.response.status_code == OkStatusSchema

    def and_status_should_be_queued_for_retry(self):
        data = self.response.json()
        assert data["status"] == "queued_for_retry"
        assert "retry_id" in data
