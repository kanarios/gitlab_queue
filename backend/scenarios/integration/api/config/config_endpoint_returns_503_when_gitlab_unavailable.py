"""Test that /api/config returns 503 when GitLab is unavailable."""

from __future__ import annotations

import vedro
from scenarios.contexts.api_helpers import created_test_app, created_test_jwt
from scenarios.schemas.status_code import ServiceUnavailableStatusSchema
from starlette.testclient import TestClient

from gitlab_queue.clients.gitlab import GitLabCircuitOpenError


class Scenario(vedro.Scenario):
    subject = "config endpoint returns 503 when gitlab unavailable"

    def given_app_with_gitlab_error(self):
        self.app, self.state = created_test_app()
        self.state.gitlab_client.get_project_web_url_error = GitLabCircuitOpenError(
            retry_after=30,
        )
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.token = created_test_jwt(self.state.settings)
        self.headers = {"Authorization": f"Bearer {self.token}"}

    def when_config_is_requested(self):
        self.response = self.client.get("/api/config", headers=self.headers)

    def then_it_should_return_503(self):
        assert self.response.status_code == ServiceUnavailableStatusSchema

    def then_response_has_retry_after_header(self):
        assert "Retry-After" in self.response.headers
