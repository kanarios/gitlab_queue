"""Test that missing OAuth config returns None or disables OAuth.

- get_oauth_config returns None when client_id is missing
- get_oauth_config returns None when client_secret is missing
- get_oauth_config returns None when redirect_uri is missing
- is_oauth_enabled returns False for incomplete config
- validate_project_access returns False for unexpected status codes
"""

from __future__ import annotations

from dataclasses import dataclass

import vedro

from gitlab_queue.auth.oauth import get_oauth_config, is_oauth_enabled, validate_project_access


@dataclass
class FakeOAuthSettings:
    """Minimal settings stub for OAuth config tests."""

    oauth_client_id: str | None = None
    oauth_client_secret: object | None = None
    oauth_redirect_uri: str | None = None
    gitlab_url: str = "https://gitlab.example.com"


class _FakeSecret:
    """Stub for SecretStr-like objects."""

    def get_secret_value(self) -> str:
        return "test-secret"


class Scenario(vedro.Scenario):
    subject = "get_oauth_config returns None when client_id is missing"

    def given_settings_without_client_id(self):
        self.settings = FakeOAuthSettings(
            oauth_client_id=None,
            oauth_client_secret=_FakeSecret(),
            oauth_redirect_uri="http://localhost/callback",
        )

    def when_get_oauth_config_is_called(self):
        self.result = get_oauth_config(self.settings)

    def then_result_is_none(self):
        assert self.result is None


class Scenario2(vedro.Scenario):
    subject = "get_oauth_config returns None when client_secret is missing"

    def given_settings_without_client_secret(self):
        self.settings = FakeOAuthSettings(
            oauth_client_id="test-client-id",
            oauth_client_secret=None,
            oauth_redirect_uri="http://localhost/callback",
        )

    def when_get_oauth_config_is_called(self):
        self.result = get_oauth_config(self.settings)

    def then_result_is_none(self):
        assert self.result is None


class Scenario3(vedro.Scenario):
    subject = "get_oauth_config returns None when redirect_uri is missing"

    def given_settings_without_redirect_uri(self):
        self.settings = FakeOAuthSettings(
            oauth_client_id="test-client-id",
            oauth_client_secret=_FakeSecret(),
            oauth_redirect_uri=None,
        )

    def when_get_oauth_config_is_called(self):
        self.result = get_oauth_config(self.settings)

    def then_result_is_none(self):
        assert self.result is None


class Scenario4(vedro.Scenario):
    subject = "is_oauth_enabled returns False for incomplete config"

    def given_settings_with_partial_oauth_config(self):
        self.settings = FakeOAuthSettings(
            oauth_client_id="test-client-id",
            oauth_client_secret=None,
            oauth_redirect_uri="http://localhost/callback",
        )

    def when_is_oauth_enabled_is_called(self):
        self.result = is_oauth_enabled(self.settings)

    def then_result_is_false(self):
        assert self.result is False


class Scenario5(vedro.Scenario):
    subject = "validate_project_access returns False for unexpected status code"

    def given_gitlab_returns_403(self):
        import httpx

        self.transport = httpx.MockTransport(lambda request: httpx.Response(403, json={"message": "Forbidden"}))

    async def when_project_access_is_validated(self):
        self.result = await validate_project_access(
            gitlab_url="https://gitlab.example.com",
            access_token="test-token",
            project_id=123,
            transport=self.transport,
        )

    def then_result_is_false(self):
        assert self.result is False
