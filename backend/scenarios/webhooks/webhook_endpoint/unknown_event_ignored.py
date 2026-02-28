"""Test that POST /webhooks/gitlab ignores unknown event types gracefully.

When a webhook event with an unrecognized object_kind is received (e.g. 'tag_push',
'note', 'build'), the endpoint should return 200 OK with status 'ignored' and
reason 'unknown_event_type'. Covers the parse_webhook_event returning None path.
"""

from __future__ import annotations

import vedro
from scenarios.contexts.api_helpers import created_test_app
from scenarios.schemas.status_code import OkStatusSchema
from starlette.testclient import TestClient


class Scenario(vedro.Scenario):
    subject = "webhook endpoint ignores unknown event type gracefully"

    def given_app(self):
        self.app, self.state = created_test_app()
        self.webhook_secret = self.state.settings.webhook_secret.get_secret_value()
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.payload = {
            "object_kind": "tag_push",
            "project": {"id": self.state.settings.gitlab_project_id},
            "ref": "refs/tags/v1.0.0",
            "user": {"id": 1, "name": "Test", "username": "test"},
        }

    def when_webhook_is_called_with_unknown_event_type(self):
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

    def and_reason_should_be_unknown_event_type(self):
        data = self.response.json()
        assert data["reason"] == "unknown_event_type"

    def and_details_should_include_object_kind(self):
        data = self.response.json()
        assert data["details"]["object_kind"] == "tag_push"
