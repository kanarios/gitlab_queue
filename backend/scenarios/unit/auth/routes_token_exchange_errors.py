"""Test error handling in token exchange endpoints.

Covers routes.py lines 166, 346-347, 355-356, 384-397:
- exchange_token returns 503 when OAuth is not configured
- _exchange_code_for_token raises 502 when no access_token in response
- _fetch_user_info raises 502 when GitLab returns non-200
- _fetch_user_info raises 502 on network error
"""

from __future__ import annotations

import secrets

import httpx
import vedro
from starlette.testclient import TestClient

from scenarios.contexts.api_helpers import create_mock_settings, created_test_app
from scenarios.unit.auth.routes._helpers import create_oauth_transport


class Scenario(vedro.Scenario):
    subject = "exchange_token returns 503 when OAuth is not configured"

    def given_app_with_oauth_disabled(self):
        self.app, self.state = created_test_app(
            settings=create_mock_settings(oauth_client_id=None),
        )
        self.client = TestClient(self.app, raise_server_exceptions=False)

    def when_token_exchange_is_requested(self):
        self.response = self.client.post(
            "/auth/token",
            params={"code": "test-code", "state": "test-state"},
        )

    def then_status_code_is_503(self):
        assert self.response.status_code == 503

    def and_detail_mentions_oauth_not_configured(self):
        data = self.response.json()
        assert "oauth not configured" in data["detail"].lower()


class ScenarioMissingAccessToken(vedro.Scenario):
    subject = "exchange_token returns 502 when access_token is missing from response"

    def given_app_with_gitlab_returning_no_access_token(self):
        self.app, self.state = created_test_app()
        self.state.oauth_transport = create_oauth_transport(
            token_response_json={"token_type": "bearer"},
        )
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.oauth_state = secrets.token_urlsafe(32)

    def when_token_exchange_is_requested(self):
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
        assert "access token" in data["detail"].lower()


class ScenarioUserInfoFetchFails(vedro.Scenario):
    subject = "exchange_token returns 502 when userinfo fetch fails"

    def given_app_with_gitlab_userinfo_failing(self):
        self.app, self.state = created_test_app()
        self.state.oauth_transport = create_oauth_transport(userinfo_status=500)
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.oauth_state = secrets.token_urlsafe(32)

    def when_token_exchange_is_requested(self):
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
        assert "failed to fetch user information" in data["detail"].lower()


class ScenarioNetworkError(vedro.Scenario):
    subject = "exchange_token returns 502 when network error during userinfo fetch"

    def given_app_with_network_error_on_userinfo(self):
        self.app, self.state = created_test_app()
        self.state.oauth_transport = create_oauth_transport(
            userinfo_error=httpx.ConnectError("Connection refused"),
        )
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.oauth_state = secrets.token_urlsafe(32)

    def when_token_exchange_is_requested(self):
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
        assert "failed to connect to gitlab" in data["detail"].lower()
