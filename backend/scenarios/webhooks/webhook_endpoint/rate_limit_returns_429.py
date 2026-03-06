"""Test that POST /webhooks/gitlab queues for retry when GitLab rate limit is exceeded.

When the webhook handler encounters a GitLabRateLimitError during event processing,
the event should be queued for retry and the response should indicate this.
Covers the generic exception handling path in handle_gitlab_webhook when
GitLab API rate limit is hit.
"""

from __future__ import annotations

import vedro
from scenarios.contexts.api_helpers import created_test_app
from scenarios.schemas.status_code import OkStatusSchema
from starlette.testclient import TestClient

from gitlab_queue.clients.gitlab import GitLabRateLimitError

from ._helpers import create_mr_webhook_payload


class Scenario(vedro.Scenario):
    subject = "webhook endpoint queues for retry when rate limit exceeded"

    def given_app(self):
        self.app, self.state = created_test_app()

        async def raise_rate_limit(state, event):
            raise GitLabRateLimitError(
                "429 Too Many Requests",
                retry_after=60,
                status_code=429,
            )

        self.state.event_router = raise_rate_limit

        self.webhook_secret = self.state.settings.webhook_secret.get_secret_value()
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.payload = create_mr_webhook_payload(
            project_id=self.state.settings.gitlab_project_id,
        )

    def when_webhook_is_called_and_rate_limit_is_hit(self):
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

    def and_retry_id_should_be_present(self):
        data = self.response.json()
        assert "retry_id" in data
