"""Test error handling for invalid/expired tokens in auth middleware.

Covers auth middleware error handling:
- TokenExpiredError returns 'Token has expired'
- InvalidTokenError returns 'Invalid token'
- Invalid Authorization header format returns error
"""

from __future__ import annotations

import vedro
from starlette.testclient import TestClient

from scenarios.contexts.api_helpers import (
    created_expired_jwt,
    created_invalid_jwt,
    created_test_app,
)


class Scenario(vedro.Scenario):
    subject = "middleware returns 401 for expired JWT token"

    def given_app_with_expired_token(self):
        """
        Set up a test application, TestClient, and attach an expired JWT token to the scenario instance.

        Initializes self.app and self.state with a test application, creates self.client (TestClient with server exceptions disabled), and stores an expired JWT in self.token for use by subsequent steps.
        """
        self.app, self.state = created_test_app()
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.token = created_expired_jwt(self.state.settings)

    def when_protected_endpoint_is_called(self):
        """
        Send a GET request to the protected /health/detailed endpoint using the scenario's token.

        Stores the HTTP response on self.response for subsequent assertions.
        """
        self.response = self.client.get(
            "/health/detailed",
            headers={"Authorization": f"Bearer {self.token}"},
        )

    def then_status_code_is_401(self):
        """
        Assert that the HTTP response status code is 401.

        Raises:
            AssertionError: If the response status code is not 401.
        """
        assert self.response.status_code == 401

    def and_detail_mentions_expired(self):
        """
        Asserts that the HTTP response's JSON "detail" field mentions "expired".

        Parses the stored response as JSON and checks that the lowercase value of the "detail" field contains the substring "expired", raising an AssertionError if it does not.
        """
        data = self.response.json()
        assert "expired" in data["detail"].lower()


class ScenarioInvalidToken(vedro.Scenario):
    subject = "middleware returns 401 for invalid JWT token"

    def given_app_with_invalid_token(self):
        """
        Prepare a test application and a TestClient configured with an invalid JWT token.

        Sets self.app and self.state to a newly created test application and state, self.client to a TestClient for that app with server exceptions disabled, and self.token to a synthetically invalid JWT.
        """
        self.app, self.state = created_test_app()
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.token = created_invalid_jwt()

    def when_protected_endpoint_is_called(self):
        """
        Send a GET request to the protected /health/detailed endpoint using the scenario's token.

        Stores the HTTP response on self.response for subsequent assertions.
        """
        self.response = self.client.get(
            "/health/detailed",
            headers={"Authorization": f"Bearer {self.token}"},
        )

    def then_status_code_is_401(self):
        """
        Assert that the HTTP response status code is 401.

        Raises:
            AssertionError: If the response status code is not 401.
        """
        assert self.response.status_code == 401

    def and_detail_mentions_invalid_token(self):
        """
        Asserts that the response JSON 'detail' field contains the word "invalid" (case-insensitive).

        Parses the response body as JSON and verifies that "invalid" appears in the `detail` value.
        """
        data = self.response.json()
        assert "invalid" in data["detail"].lower()


class ScenarioMissingAuth(vedro.Scenario):
    subject = "middleware returns 401 for missing Authorization header"

    def given_app_with_no_auth_header(self):
        """
        Create a test application and HTTP client configured for requests that omit the Authorization header.

        Initializes self.app and self.state using the test app factory and sets self.client to a TestClient for the app with server exceptions disabled so responses (including error responses) can be inspected by subsequent steps.
        """
        self.app, self.state = created_test_app()
        self.client = TestClient(self.app, raise_server_exceptions=False)

    def when_protected_endpoint_is_called_without_auth(self):
        """
        Send a GET request to the protected /health/detailed endpoint without an Authorization header.

        Sets self.response to the HTTP response returned by the test client.
        """
        self.response = self.client.get("/health/detailed")

    def then_status_code_is_401(self):
        """
        Assert that the HTTP response status code is 401.

        Raises:
            AssertionError: If the response status code is not 401.
        """
        assert self.response.status_code == 401

    def and_detail_mentions_missing_authorization(self):
        """
        Asserts that the response detail indicates a missing Authorization header.

        Raises an AssertionError if the response JSON `detail` field does not contain
        "authorization" or "missing" (case-insensitive).
        """
        data = self.response.json()
        assert "authorization" in data["detail"].lower() or "missing" in data["detail"].lower()


class ScenarioMalformedAuth(vedro.Scenario):
    subject = "middleware returns 401 for malformed Authorization header"

    def given_app_with_malformed_auth_header(self):
        """
        Prepare a test application and HTTP client for the malformed Authorization header scenario.

        Creates the test app and state using created_test_app() and instantiates a TestClient configured with raise_server_exceptions=False so responses can be inspected without raising server exceptions.
        """
        self.app, self.state = created_test_app()
        self.client = TestClient(self.app, raise_server_exceptions=False)

    def when_protected_endpoint_is_called_with_bad_format(self):
        """
        Call the protected /health/detailed endpoint with a malformed Authorization header and save the HTTP response on self.response.

        The Authorization header uses an incorrect scheme ("NotBearer sometoken") to trigger authentication middleware handling.
        """
        self.response = self.client.get(
            "/health/detailed",
            headers={"Authorization": "NotBearer sometoken"},
        )

    def then_status_code_is_401(self):
        """
        Assert that the HTTP response status code is 401.

        Raises:
            AssertionError: If the response status code is not 401.
        """
        assert self.response.status_code == 401

    def and_detail_mentions_invalid_format(self):
        """
        Asserts that the JSON response's "detail" message indicates an invalid format.

        Checks the test response's JSON body and asserts that the "detail" field contains the word "format" (case-insensitive). Raises AssertionError if the expectation is not met.
        """
        data = self.response.json()
        assert "format" in data["detail"].lower()
