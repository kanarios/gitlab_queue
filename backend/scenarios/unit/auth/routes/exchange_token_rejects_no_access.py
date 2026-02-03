"""Test that POST /auth/token returns 403 when user has no project access."""

from __future__ import annotations

import secrets
from unittest.mock import AsyncMock, patch

import vedro
from scenarios.contexts.api_helpers import created_test_app
from scenarios.schemas.status_code import ForbiddenStatusSchema
from starlette.testclient import TestClient

from ._helpers import create_mock_httpx_client


class Scenario(vedro.Scenario):
    subject = "exchange token rejects user without project access"

    def given_app_with_no_project_access(self):
        self.app, self.state = created_test_app()
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.oauth_state = secrets.token_urlsafe(32)
        self.mock_httpx_client = create_mock_httpx_client()

    def when_token_is_exchanged_without_access(self):
        with (
            patch(
                "gitlab_queue.auth.routes.httpx.AsyncClient",
                return_value=self.mock_httpx_client,
            ),
            patch(
                "gitlab_queue.auth.routes.validate_project_access",
                new_callable=AsyncMock,
                return_value=False,
            ),
        ):
            self.response = self.client.post(
                "/auth/token",
                params={
                    "code": "test-auth-code",
                    "state": self.oauth_state,
                },
                cookies={"oauth_state": self.oauth_state},
            )

    def then_it_should_return_403(self):
        assert self.response.status_code == ForbiddenStatusSchema

    def and_detail_should_mention_access_denied(self):
        data = self.response.json()
        assert "access denied" in data["detail"].lower() or "access" in data["detail"].lower()
