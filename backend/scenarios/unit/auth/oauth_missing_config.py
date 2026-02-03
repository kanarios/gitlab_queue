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
        self.settings = MagicMock()
        self.settings.oauth_client_id = None
        self.settings.oauth_client_secret = MagicMock()
        self.settings.oauth_redirect_uri = "http://localhost/callback"

    def when_get_oauth_config_is_called(self):
        self.result = get_oauth_config(self.settings)

    def then_result_is_none(self):
        assert self.result is None


class Scenario2(vedro.Scenario):
    subject = "get_oauth_config returns None when client_secret is missing"

    def given_settings_without_client_secret(self):
        self.settings = MagicMock()
        self.settings.oauth_client_id = "test-client-id"
        self.settings.oauth_client_secret = None
        self.settings.oauth_redirect_uri = "http://localhost/callback"

    def when_get_oauth_config_is_called(self):
        self.result = get_oauth_config(self.settings)

    def then_result_is_none(self):
        assert self.result is None


class Scenario3(vedro.Scenario):
    subject = "get_oauth_config returns None when redirect_uri is missing"

    def given_settings_without_redirect_uri(self):
        self.settings = MagicMock()
        self.settings.oauth_client_id = "test-client-id"
        self.settings.oauth_client_secret = MagicMock()
        self.settings.oauth_redirect_uri = None

    def when_get_oauth_config_is_called(self):
        self.result = get_oauth_config(self.settings)

    def then_result_is_none(self):
        assert self.result is None


class Scenario4(vedro.Scenario):
    subject = "is_oauth_enabled returns False for incomplete config"

    def given_settings_with_partial_oauth_config(self):
        self.settings = MagicMock()
        self.settings.oauth_client_id = "test-client-id"
        self.settings.oauth_client_secret = None
        self.settings.oauth_redirect_uri = "http://localhost/callback"

    def when_is_oauth_enabled_is_called(self):
        self.result = is_oauth_enabled(self.settings)

    def then_result_is_false(self):
        assert self.result is False


class Scenario5(vedro.Scenario):
    subject = "validate_project_access returns False for unexpected status code"

    def given_gitlab_returns_403(self):
        self.mock_response = MagicMock()
        self.mock_response.status_code = 403
        self.mock_client = AsyncMock()
        self.mock_client.get = AsyncMock(return_value=self.mock_response)
        self.mock_client.__aenter__ = AsyncMock(return_value=self.mock_client)
        self.mock_client.__aexit__ = AsyncMock(return_value=None)

    async def when_project_access_is_validated(self):
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
        assert self.result is False
