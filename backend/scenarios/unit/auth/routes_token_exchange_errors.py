"""Test error handling in token exchange endpoints.

Covers routes.py lines 166, 346-347, 355-356, 384-397:
- exchange_token returns 503 when OAuth is not configured
- _exchange_code_for_token raises 502 when no access_token in response
- _fetch_user_info raises 502 when GitLab returns non-200
- _fetch_user_info raises 502 on network error
"""

from __future__ import annotations

import secrets
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import vedro
from scenarios.contexts.api_helpers import created_test_app
from scenarios.unit.auth.routes._helpers import create_mock_httpx_client
from starlette.testclient import TestClient


class Scenario(vedro.Scenario):
    subject = "exchange_token returns 503 when OAuth is not configured"

    def given_app_with_oauth_disabled(self):
        self.app, self.state = created_test_app()
        self.client = TestClient(self.app, raise_server_exceptions=False)

    def when_token_exchange_is_requested(self):
        with patch(
            "gitlab_queue.auth.routes.get_oauth_config",
            return_value=None,
        ):
            self.response = self.client.post(
                "/auth/token",
                params={"code": "test-code", "state": "test-state"},
            )

    def then_status_code_is_503(self):
        assert self.response.status_code == 503

    def and_detail_mentions_oauth_not_configured(self):
        data = self.response.json()
        assert "oauth" in data["detail"].lower() or "not configured" in data["detail"].lower()


class ScenarioMissingAccessToken(vedro.Scenario):
    subject = "exchange_token returns 502 when access_token is missing from response"

    def given_app_with_gitlab_returning_no_access_token(self):
        self.app, self.state = created_test_app()
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.oauth_state = secrets.token_urlsafe(32)

        # Mock httpx client: token response has no access_token
        token_response = MagicMock()
        token_response.status_code = 200
        token_response.json.return_value = {"token_type": "bearer"}  # no access_token
        self.mock_client = create_mock_httpx_client(token_response=token_response)

    def when_token_exchange_is_requested(self):
        with patch(
            "gitlab_queue.auth.routes.httpx.AsyncClient",
            return_value=self.mock_client,
        ):
            self.response = self.client.post(
                "/auth/token",
                params={
                    "code": "valid-code",
                    "state": self.oauth_state,
                },
                cookies={"oauth_state": self.oauth_state},
            )

    def then_status_code_is_502(self):
        assert self.response.status_code == 502

    def and_detail_mentions_no_access_token(self):
        data = self.response.json()
        assert "access token" in data["detail"].lower() or "token" in data["detail"].lower()


class ScenarioUserInfoFetchFails(vedro.Scenario):
    subject = "exchange_token returns 502 when userinfo fetch fails"

    def given_app_with_gitlab_userinfo_failing(self):
        self.app, self.state = created_test_app()
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.oauth_state = secrets.token_urlsafe(32)

        # Token exchange succeeds, but user info returns 500
        userinfo_response = MagicMock()
        userinfo_response.status_code = 500
        self.mock_client = create_mock_httpx_client(userinfo_response=userinfo_response)

    def when_token_exchange_is_requested(self):
        with patch(
            "gitlab_queue.auth.routes.httpx.AsyncClient",
            return_value=self.mock_client,
        ):
            self.response = self.client.post(
                "/auth/token",
                params={
                    "code": "valid-code",
                    "state": self.oauth_state,
                },
                cookies={"oauth_state": self.oauth_state},
            )

    def then_status_code_is_502(self):
        assert self.response.status_code == 502

    def and_detail_mentions_user_info_failure(self):
        data = self.response.json()
        assert "user" in data["detail"].lower() or "failed" in data["detail"].lower()


class ScenarioNetworkError(vedro.Scenario):
    subject = "exchange_token returns 502 when network error during userinfo fetch"

    def given_app_with_network_error_on_userinfo(self):
        self.app, self.state = created_test_app()
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.oauth_state = secrets.token_urlsafe(32)

        # Token exchange succeeds, but user info raises network error
        self.mock_client = create_mock_httpx_client()
        self.mock_client.get = AsyncMock(
            side_effect=httpx.ConnectError("Connection refused"),
        )

    def when_token_exchange_is_requested(self):
        with patch(
            "gitlab_queue.auth.routes.httpx.AsyncClient",
            return_value=self.mock_client,
        ):
            self.response = self.client.post(
                "/auth/token",
                params={
                    "code": "valid-code",
                    "state": self.oauth_state,
                },
                cookies={"oauth_state": self.oauth_state},
            )

    def then_status_code_is_502(self):
        assert self.response.status_code == 502

    def and_detail_mentions_connection_failure(self):
        data = self.response.json()
        assert "connect" in data["detail"].lower() or "failed" in data["detail"].lower()
