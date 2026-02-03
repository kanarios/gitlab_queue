"""Test that POST /auth/token returns a JWT when code is exchanged successfully."""

from __future__ import annotations

import secrets
from unittest.mock import AsyncMock, patch

import vedro
from scenarios.contexts.api_helpers import created_test_app
from scenarios.schemas.status_code import OkStatusSchema
from starlette.testclient import TestClient

from ._helpers import create_mock_httpx_client


class Scenario(vedro.Scenario):
    subject = "exchange token returns JWT on successful authentication"

    def given_app_with_mocked_oauth(self):
        self.app, self.state = created_test_app()
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.oauth_state = secrets.token_urlsafe(32)
        self.mock_httpx_client = create_mock_httpx_client()

    def when_token_is_exchanged(self):
        with (
            patch(
                "gitlab_queue.auth.routes.httpx.AsyncClient",
                return_value=self.mock_httpx_client,
            ),
            patch(
                "gitlab_queue.auth.routes.validate_project_access",
                new_callable=AsyncMock,
                return_value=True,
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

    def then_it_should_return_200(self):
        assert self.response.status_code == OkStatusSchema

    def and_response_should_contain_access_token(self):
        data = self.response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def and_response_should_contain_user_info(self):
        data = self.response.json()
        assert "user" in data
        assert data["user"]["username"] == "testuser"
        assert data["user"]["id"] == 1
