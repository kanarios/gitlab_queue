"""Test that POST /webhooks/gitlab queues for retry when payload parsing fails.

When a webhook event with a known object_kind (e.g. merge_request) arrives but
cannot be parsed due to missing or malformed fields, the endpoint should queue
it for retry in the DLQ and return a 200 with status 'queued_for_retry'.
Covers router.py parse error handling path (ValueError/KeyError catch block).
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import vedro
from scenarios.contexts.api_helpers import created_test_app
from scenarios.schemas.status_code import OkStatusSchema
from starlette.testclient import TestClient


class Scenario(vedro.Scenario):
    subject = "webhook endpoint queues parse error for retry"

    def given_app_with_valid_token(self):
        self.app, self.state = created_test_app()
        self.webhook_secret = self.state.settings.webhook_secret.get_secret_value()
        self.state.retry_manager.add_to_retry_queue = AsyncMock(return_value=7)
        self.client = TestClient(self.app, raise_server_exceptions=False)
        # Pipeline event with missing required fields to trigger parse error
        self.payload = {
            "object_kind": "pipeline",
            "project": {"id": self.state.settings.gitlab_project_id},
            # Missing object_attributes, merge_request, etc.
        }

    def when_webhook_is_called_with_unparseable_payload(self):
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

    def and_retry_manager_should_be_called(self):
        self.state.retry_manager.add_to_retry_queue.assert_called_once()
        call_kwargs = self.state.retry_manager.add_to_retry_queue.call_args.kwargs
        assert call_kwargs["event_type"] == "pipeline"
