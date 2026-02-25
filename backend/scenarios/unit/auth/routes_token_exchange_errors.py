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
        """
        Set up a test application with OAuth disabled and initialize a TestClient.
        
        Assigns `self.app` and `self.state` using `created_test_app()` and creates `self.client` as a TestClient for `self.app` with `raise_server_exceptions=False`.
        """
        self.app, self.state = created_test_app()
        self.client = TestClient(self.app, raise_server_exceptions=False)

    def when_token_exchange_is_requested(self):
        """
        Send a token exchange POST to /auth/token while OAuth is not configured and store the HTTP response on self.response.
        
        The request uses code "test-code" and state "test-state" to simulate the token exchange attempt when OAuth configuration is missing.
        """
        with patch(
            "gitlab_queue.auth.routes.get_oauth_config",
            return_value=None,
        ):
            self.response = self.client.post(
                "/auth/token",
                params={"code": "test-code", "state": "test-state"},
            )

    def then_status_code_is_503(self):
        """
        Assert that the stored HTTP response has status code 503 (Service Unavailable).
        
        This verifies the token exchange endpoint responded with a 503 when OAuth is not configured.
        """
        assert self.response.status_code == 503

    def and_detail_mentions_oauth_not_configured(self):
        """
        Asserts that the response detail message refers to OAuth being missing or not configured.
        
        Parses the JSON body of the stored response and checks that the "detail" field (case-insensitive) contains either "oauth" or "not configured".
        
        Raises:
            AssertionError: If the response JSON does not contain a "detail" mentioning OAuth or not being configured.
        """
        data = self.response.json()
        assert "oauth" in data["detail"].lower() or "not configured" in data["detail"].lower()


class ScenarioMissingAccessToken(vedro.Scenario):
    subject = "exchange_token returns 502 when access_token is missing from response"

    def given_app_with_gitlab_returning_no_access_token(self):
        """
        Prepare a test application and HTTP client that simulates a GitLab token response missing an access token.
        
        Sets up self.app and self.state via created_test_app(), a TestClient assigned to self.client, a generated OAuth state in self.oauth_state, and a mock HTTPX client in self.mock_client whose token response has status 200 but no `access_token` in its JSON payload.
        """
        self.app, self.state = created_test_app()
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.oauth_state = secrets.token_urlsafe(32)

        # Mock httpx client: token response has no access_token
        token_response = MagicMock()
        token_response.status_code = 200
        token_response.json.return_value = {"token_type": "bearer"}  # no access_token
        self.mock_client = create_mock_httpx_client(token_response=token_response)

    def when_token_exchange_is_requested(self):
        """
        Send a token exchange POST to /auth/token using the prepared mock HTTP client.
        
        Patches gitlab_queue.auth.routes.httpx.AsyncClient to return self.mock_client, performs a POST with code and state parameters and the oauth_state cookie, and stores the HTTP response on self.response.
        """
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
        """
        Asserts that the most recent HTTP response returned status code 502 (Bad Gateway).
        
        This is used in scenarios validating that the token exchange endpoint reports a 502 error for upstream or processing failures.
        """
        assert self.response.status_code == 502

    def and_detail_mentions_no_access_token(self):
        """
        Asserts that the response error detail mentions a missing access token.
        
        Raises:
        	AssertionError: If the response JSON `detail` does not contain "access token" or "token" (case-insensitive).
        """
        data = self.response.json()
        assert "access token" in data["detail"].lower() or "token" in data["detail"].lower()


class ScenarioUserInfoFetchFails(vedro.Scenario):
    subject = "exchange_token returns 502 when userinfo fetch fails"

    def given_app_with_gitlab_userinfo_failing(self):
        """
        Set up a test application and a mocked HTTPX client where the token exchange succeeds but the userinfo endpoint returns HTTP 500.
        
        Initializes:
        - self.app, self.state: test application and state
        - self.client: TestClient for the app (server exceptions suppressed)
        - self.oauth_state: a generated OAuth state string
        - self.mock_client: an HTTPX AsyncClient mock configured to return a 500 status for the userinfo request
        """
        self.app, self.state = created_test_app()
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.oauth_state = secrets.token_urlsafe(32)

        # Token exchange succeeds, but user info returns 500
        userinfo_response = MagicMock()
        userinfo_response.status_code = 500
        self.mock_client = create_mock_httpx_client(userinfo_response=userinfo_response)

    def when_token_exchange_is_requested(self):
        """
        Send a token exchange POST to /auth/token using the prepared mock HTTP client.
        
        Patches gitlab_queue.auth.routes.httpx.AsyncClient to return self.mock_client, performs a POST with code and state parameters and the oauth_state cookie, and stores the HTTP response on self.response.
        """
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
        """
        Asserts that the most recent HTTP response returned status code 502 (Bad Gateway).
        
        This is used in scenarios validating that the token exchange endpoint reports a 502 error for upstream or processing failures.
        """
        assert self.response.status_code == 502

    def and_detail_mentions_user_info_failure(self):
        """
        Asserts that the response error detail indicates a user info fetch failure.
        
        Raises:
            AssertionError: if the response JSON `detail` does not contain "user" or "failed" (case-insensitive).
        """
        data = self.response.json()
        assert "user" in data["detail"].lower() or "failed" in data["detail"].lower()


class ScenarioNetworkError(vedro.Scenario):
    subject = "exchange_token returns 502 when network error during userinfo fetch"

    def given_app_with_network_error_on_userinfo(self):
        """
        Prepare a test application configured so the token exchange proceeds but the userinfo request raises a network connection error.
        
        Sets the following instance attributes used by subsequent steps:
        - app: the TestApp instance.
        - state: application state returned by created_test_app().
        - client: TestClient for sending requests to the app.
        - oauth_state: a random OAuth state string stored in a cookie during the test.
        - mock_client: an HTTPX AsyncClient mock whose `get` method raises httpx.ConnectError("Connection refused") to simulate a network failure when fetching user info.
        """
        self.app, self.state = created_test_app()
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.oauth_state = secrets.token_urlsafe(32)

        # Token exchange succeeds, but user info raises network error
        self.mock_client = create_mock_httpx_client()
        self.mock_client.get = AsyncMock(
            side_effect=httpx.ConnectError("Connection refused"),
        )

    def when_token_exchange_is_requested(self):
        """
        Send a token exchange POST to /auth/token using the prepared mock HTTP client.
        
        Patches gitlab_queue.auth.routes.httpx.AsyncClient to return self.mock_client, performs a POST with code and state parameters and the oauth_state cookie, and stores the HTTP response on self.response.
        """
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
        """
        Asserts that the most recent HTTP response returned status code 502 (Bad Gateway).
        
        This is used in scenarios validating that the token exchange endpoint reports a 502 error for upstream or processing failures.
        """
        assert self.response.status_code == 502

    def and_detail_mentions_connection_failure(self):
        """
        Asserts that the response detail indicates a connection failure.
        
        Checks the JSON response's "detail" field and verifies it contains either "connect" or "failed" (case-insensitive).
        """
        data = self.response.json()
        assert "connect" in data["detail"].lower() or "failed" in data["detail"].lower()
