"""Test that POST /webhooks/gitlab rejects an invalid webhook token."""

from __future__ import annotations

import vedro
from scenarios.contexts.api_helpers import created_test_app
from scenarios.schemas.status_code import UnauthorizedStatusSchema
from starlette.testclient import TestClient

from ._helpers import create_mr_webhook_payload


class Scenario(vedro.Scenario):
    subject = "webhook endpoint rejects invalid token"

    def given_app(self):
        self.app, self.state = created_test_app()
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.payload = create_mr_webhook_payload(
            project_id=self.state.settings.gitlab_project_id,
        )

    def when_webhook_is_called_with_wrong_token(self):
        self.response = self.client.post(
            "/webhooks/gitlab",
            json=self.payload,
            headers={"X-Gitlab-Token": "wrong-secret-token"},
        )

    def then_it_should_return_401(self):
        assert self.response.status_code == UnauthorizedStatusSchema
