"""Test that POST /auth/token handles GitLab token exchange error."""

from __future__ import annotations

import secrets
from unittest.mock import AsyncMock, MagicMock, patch

import vedro
from scenarios.contexts.api_helpers import created_test_app
from starlette.testclient import TestClient


class Scenario(vedro.Scenario):
    subject = "exchange token handles GitLab error gracefully"

    def given_app_with_failing_gitlab(self):
        """
        Set up a test application and an AsyncClient mock that simulates a failed GitLab token exchange.
        
        Initializes a test app and TestClient, generates an OAuth state, and creates self.mock_client whose POST returns a response with status_code 400 and text "invalid_grant". The mock also implements async context manager methods so it can be used with "async with".
        """
        self.app, self.state = created_test_app()
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.oauth_state = secrets.token_urlsafe(32)
        # Create a mock client that returns a failed token exchange
        self.mock_client = AsyncMock()
        failed_response = MagicMock()
        failed_response.status_code = 400
        failed_response.text = "invalid_grant"
        self.mock_client.post = AsyncMock(return_value=failed_response)
        self.mock_client.__aenter__ = AsyncMock(return_value=self.mock_client)
        self.mock_client.__aexit__ = AsyncMock(return_value=None)

    def when_token_exchange_fails(self):
        with patch(
            "gitlab_queue.auth.routes.httpx.AsyncClient",
            return_value=self.mock_client,
        ):
            self.response = self.client.post(
                "/auth/token",
                params={
                    "code": "invalid-code",
                    "state": self.oauth_state,
                },
                cookies={"oauth_state": self.oauth_state},
            )

    def then_it_should_return_error_status(self):
        # 502 Bad Gateway when GitLab returns non-200
        """
        Assert that the HTTP response status code is 502 Bad Gateway.
        
        Raises:
            AssertionError: If the response status code is not 502.
        """
        assert self.response.status_code == 502

    def and_detail_should_indicate_failure(self):
        """
        Assert that the response JSON 'detail' indicates a token exchange failure.
        
        Raises:
            AssertionError: If the response JSON `detail` field does not contain "failed" or "token" (case-insensitive).
        """
        data = self.response.json()
        assert "failed" in data["detail"].lower() or "token" in data["detail"].lower()
