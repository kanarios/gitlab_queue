"""Test that POST /auth/token returns a JWT when code is exchanged successfully."""

from __future__ import annotations

import secrets
from unittest.mock import AsyncMock, patch

import vedro
from starlette.testclient import TestClient

from scenarios.contexts.api_helpers import created_test_app
from scenarios.schemas.status_code import OkStatusSchema

from ._helpers import create_mock_httpx_client


class Scenario(vedro.Scenario):
    subject = "exchange token returns JWT on successful authentication"

    def given_app_with_mocked_oauth(self):
        """
        Prepare a test application and related test fixtures for the scenario.

        Sets the following instance attributes used by later steps:
        - app: the created test ASGI application.
        - state: application state returned by created_test_app().
        - client: TestClient for making HTTP requests against the app.
        - oauth_state: a random OAuth state string for CSRF/session simulation.
        - mock_httpx_client: a mocked httpx.AsyncClient configured for external OAuth calls.
        """
        self.app, self.state = created_test_app()
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.oauth_state = secrets.token_urlsafe(32)
        self.mock_httpx_client = create_mock_httpx_client()

    def when_token_is_exchanged(self):
        """
        Execute a token-exchange POST to /auth/token while mocking external OAuth dependencies and store the HTTP response.

        Sends a POST request with `code="test-auth-code"` and `state` taken from `self.oauth_state`, providing the same value in cookies; during the request, the external HTTP client and project-access validation are mocked. The resulting response is saved on `self.response`.
        """
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
        """
        Assert that the stored HTTP response has status code 200 (OK).

        Raises:
            AssertionError: if the response status code is not 200.
        """
        assert self.response.status_code == OkStatusSchema

    def and_response_should_contain_access_token(self):
        """
        Asserts the HTTP response JSON contains an OAuth access token and a bearer token type.

        Parses the response stored on the test instance and verifies that the top-level
        key "access_token" is present and that "token_type" equals "bearer".
        """
        data = self.response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def and_response_should_contain_user_info(self):
        """
        Asserts the HTTP response JSON contains a user object with the expected username and id.

        Checks that the top-level "user" key exists, that the user's "username" equals "testuser", and that the user's "id" equals 1.
        """
        data = self.response.json()
        assert "user" in data
        assert data["user"]["username"] == "testuser"
        assert data["user"]["id"] == 1
