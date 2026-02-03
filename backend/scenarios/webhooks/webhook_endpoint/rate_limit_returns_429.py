"""Test that POST /webhooks/gitlab queues for retry when GitLab rate limit is exceeded.

When the webhook handler encounters a GitLabRateLimitError during event processing,
the event should be queued for retry and the response should indicate this.
Covers the generic exception handling path in handle_gitlab_webhook when
GitLab API rate limit is hit.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

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
        self.webhook_secret = self.state.settings.webhook_secret.get_secret_value()
        self.state.retry_manager.add_to_retry_queue = AsyncMock(return_value=99)
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.payload = create_mr_webhook_payload(
            project_id=self.state.settings.gitlab_project_id,
        )

    def when_webhook_is_called_and_rate_limit_is_hit(self):
        with patch(
            "gitlab_queue.webhooks.router._route_webhook_event",
            new_callable=AsyncMock,
            side_effect=GitLabRateLimitError(
                "429 Too Many Requests",
                retry_after=60,
                status_code=429,
            ),
        ):
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
