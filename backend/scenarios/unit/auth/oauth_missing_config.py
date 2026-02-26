"""Test that missing OAuth config returns None or disables OAuth.

Covers oauth.py lines 93, 95, 122, 182-187:
- get_oauth_config returns None when client_id is missing
- get_oauth_config returns None when client_secret is missing
- get_oauth_config returns None when redirect_uri is missing
- is_oauth_enabled returns False for incomplete config
- validate_project_access returns False for unexpected status codes
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import vedro

from gitlab_queue.auth.oauth import get_oauth_config, is_oauth_enabled, validate_project_access


class Scenario(vedro.Scenario):
    subject = "get_oauth_config returns None when client_id is missing"

    def given_settings_without_client_id(self):
        """
        Prepare a MagicMock settings object with an absent OAuth client ID and otherwise populated OAuth fields.

        Sets self.settings to a MagicMock with:
        - oauth_client_id = None
        - oauth_client_secret mocked
        - oauth_redirect_uri set to "http://localhost/callback"
        """
        self.settings = MagicMock()
        self.settings.oauth_client_id = None
        self.settings.oauth_client_secret = MagicMock()
        self.settings.oauth_redirect_uri = "http://localhost/callback"

    def when_get_oauth_config_is_called(self):
        """
        Call get_oauth_config with the scenario's settings and store the returned value on self.result.
        """
        self.result = get_oauth_config(self.settings)

    def then_result_is_none(self):
        """
        Asserts that the scenario's result is None.

        Raises:
            AssertionError: If `self.result` is not None.
        """
        assert self.result is None


class Scenario2(vedro.Scenario):
    subject = "get_oauth_config returns None when client_secret is missing"

    def given_settings_without_client_secret(self):
        """
        Configure self.settings as a MagicMock representing OAuth settings with a client ID and redirect URI but no client secret.

        Sets:
            self.settings.oauth_client_id = "test-client-id"
            self.settings.oauth_client_secret = None
            self.settings.oauth_redirect_uri = "http://localhost/callback"
        """
        self.settings = MagicMock()
        self.settings.oauth_client_id = "test-client-id"
        self.settings.oauth_client_secret = None
        self.settings.oauth_redirect_uri = "http://localhost/callback"

    def when_get_oauth_config_is_called(self):
        """
        Call get_oauth_config with the scenario's settings and store the returned value on self.result.
        """
        self.result = get_oauth_config(self.settings)

    def then_result_is_none(self):
        """
        Asserts that the scenario's result is None.

        Raises:
            AssertionError: If `self.result` is not None.
        """
        assert self.result is None


class Scenario3(vedro.Scenario):
    subject = "get_oauth_config returns None when redirect_uri is missing"

    def given_settings_without_redirect_uri(self):
        """
        Prepare self.settings with an OAuth client ID and secret while leaving the redirect URI unset.

        Sets:
            self.settings.oauth_client_id to "test-client-id"
            self.settings.oauth_client_secret to a MagicMock instance
            self.settings.oauth_redirect_uri to None
        """
        self.settings = MagicMock()
        self.settings.oauth_client_id = "test-client-id"
        self.settings.oauth_client_secret = MagicMock()
        self.settings.oauth_redirect_uri = None

    def when_get_oauth_config_is_called(self):
        """
        Call get_oauth_config with the scenario's settings and store the returned value on self.result.
        """
        self.result = get_oauth_config(self.settings)

    def then_result_is_none(self):
        """
        Asserts that the scenario's result is None.

        Raises:
            AssertionError: If `self.result` is not None.
        """
        assert self.result is None


class Scenario4(vedro.Scenario):
    subject = "is_oauth_enabled returns False for incomplete config"

    def given_settings_with_partial_oauth_config(self):
        """
        Configure the scenario's settings with a partially populated OAuth configuration.

        Sets self.settings to a MagicMock and assigns:
        - oauth_client_id: "test-client-id"
        - oauth_client_secret: None
        - oauth_redirect_uri: "http://localhost/callback"
        """
        self.settings = MagicMock()
        self.settings.oauth_client_id = "test-client-id"
        self.settings.oauth_client_secret = None
        self.settings.oauth_redirect_uri = "http://localhost/callback"

    def when_is_oauth_enabled_is_called(self):
        self.result = is_oauth_enabled(self.settings)

    def then_result_is_false(self):
        """
        Assert that the stored result is False.
        """
        assert self.result is False


class Scenario5(vedro.Scenario):
    subject = "validate_project_access returns False for unexpected status code"

    def given_gitlab_returns_403(self):
        """
        Prepare mocked HTTP client and response to simulate a GitLab 403 (Forbidden) response.

        Sets:
        - self.mock_response: MagicMock with .status_code = 403.
        - self.mock_client: AsyncMock whose .get returns self.mock_response and whose async context manager methods (__aenter__, __aexit__) are configured to enter/exit returning the client and None respectively.
        """
        self.mock_response = MagicMock()
        self.mock_response.status_code = 403
        self.mock_client = AsyncMock()
        self.mock_client.get = AsyncMock(return_value=self.mock_response)
        self.mock_client.__aenter__ = AsyncMock(return_value=self.mock_client)
        self.mock_client.__aexit__ = AsyncMock(return_value=None)

    async def when_project_access_is_validated(self):
        """
        Trigger project access validation and store its outcome on self.result.

        Patches httpx.AsyncClient to return self.mock_client, calls validate_project_access with gitlab_url "https://gitlab.example.com", access_token "test-token", and project_id 123, and assigns the returned boolean to self.result.
        """
        with patch(
            "gitlab_queue.auth.oauth.httpx.AsyncClient",
            return_value=self.mock_client,
        ):
            self.result = await validate_project_access(
                gitlab_url="https://gitlab.example.com",
                access_token="test-token",
                project_id=123,
            )

    def then_result_is_false(self):
        """
        Assert that the stored result is False.
        """
        assert self.result is False
