"""Test that POST /auth/token returns 403 when user has no project access."""

from __future__ import annotations

import secrets
from unittest.mock import AsyncMock, patch

import vedro
from starlette.testclient import TestClient

from scenarios.contexts.api_helpers import created_test_app
from scenarios.schemas.status_code import ForbiddenStatusSchema

from ._helpers import create_mock_httpx_client


class Scenario(vedro.Scenario):
    subject = "exchange token rejects user without project access"

    def given_app_with_no_project_access(self):
        """
        Initialize test fixtures representing an application where the current user lacks project access.

        Sets self.app and self.state using created_test_app(), creates a TestClient (with server exceptions suppressed) and stores it on self.client, generates and stores an OAuth state token on self.oauth_state, and creates a mocked HTTPX client assigned to self.mock_httpx_client.
        """
        self.app, self.state = created_test_app()
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.oauth_state = secrets.token_urlsafe(32)
        self.mock_httpx_client = create_mock_httpx_client()

    def when_token_is_exchanged_without_access(self):
        """
        Simulates exchanging an OAuth token when the user lacks project access and records the HTTP response.

        Patches the HTTPX AsyncClient to use the test mock client and makes validate_project_access return False, then POSTs to /auth/token with a code and state and stores the resulting response on self.response.
        """
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
        """
        Asserts that the received HTTP response has the forbidden status code.

        The assertion fails (raises AssertionError) if the response status code is not equal to ForbiddenStatusSchema.
        """
        assert self.response.status_code == ForbiddenStatusSchema

    def and_detail_should_mention_access_denied(self):
        """
        Verify that the response detail message indicates access was denied.

        Asserts that the response JSON's "detail" field contains either "access denied" or "access" (case-insensitive), raising an AssertionError if the check fails.
        """
        data = self.response.json()
        assert "access denied" in data["detail"].lower()
