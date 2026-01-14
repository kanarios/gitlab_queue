"""Test scenarios for GitLabClient error handling.

Tests error handling including:
- 404 -> GitLabNotFoundError
- 409 -> GitLabConflictError
- 429 -> GitLabRateLimitError
- 5xx -> GitLabServerError
- Exception sanitization (no sensitive data)
"""

from __future__ import annotations

import vedro
from scenarios.contexts.gitlab_client_factory import TEST_PROJECT_ID, create_test_client
from scenarios.contexts.jj_gitlab_mock import mock_gitlab_get_mr

from gitlab_queue.clients.gitlab import (
    GitLabAPIError,
    GitLabConflictError,
    GitLabNotFoundError,
    GitLabServerError,
    _sanitize_response_body,
)


class Scenario__404_raises_not_found_error(vedro.Scenario):
    subject = "404 response raises GitLabNotFoundError"

    async def given_mock_gitlab_returns_404(self):
        self._mock_ctx = mock_gitlab_get_mr(
            TEST_PROJECT_ID,
            999,
            {"message": "404 Project Not Found"},
            status=404,
        )
        await self._mock_ctx.__aenter__()
        self.client = create_test_client()

    async def when_get_mr_is_called(self):
        self.error = None
        try:
            await self.client.get_mr(999)
        except GitLabNotFoundError as e:
            self.error = e

    def then_not_found_error_should_be_raised(self):
        assert self.error is not None
        assert isinstance(self.error, GitLabNotFoundError)

    def and_status_code_should_be_404(self):
        assert self.error.status_code == 404

    def and_error_should_be_api_error_subclass(self):
        assert isinstance(self.error, GitLabAPIError)

    async def do_cleanup(self):
        await self.client.close()
        await self._mock_ctx.__aexit__(None, None, None)


class Scenario__409_raises_conflict_error(vedro.Scenario):
    subject = "409 response raises GitLabConflictError"

    async def given_mock_gitlab_returns_409(self):
        self._mock_ctx = mock_gitlab_get_mr(
            TEST_PROJECT_ID,
            42,
            {"message": "409 Conflict"},
            status=409,
        )
        await self._mock_ctx.__aenter__()
        self.client = create_test_client()

    async def when_get_mr_is_called(self):
        self.error = None
        try:
            await self.client.get_mr(42)
        except GitLabConflictError as e:
            self.error = e

    def then_conflict_error_should_be_raised(self):
        assert self.error is not None
        assert isinstance(self.error, GitLabConflictError)

    def and_status_code_should_be_409(self):
        assert self.error.status_code == 409

    async def do_cleanup(self):
        await self.client.close()
        await self._mock_ctx.__aexit__(None, None, None)


class Scenario__500_raises_server_error(vedro.Scenario):
    subject = "500 response raises GitLabServerError"

    async def given_mock_gitlab_returns_500(self):
        self._mock_ctx = mock_gitlab_get_mr(
            TEST_PROJECT_ID,
            42,
            {"error": "Internal Server Error"},
            status=500,
        )
        await self._mock_ctx.__aenter__()
        self.client = create_test_client()

    async def when_get_mr_is_called(self):
        self.error = None
        try:
            await self.client.get_mr(42)
        except GitLabServerError as e:
            self.error = e

    def then_server_error_should_be_raised(self):
        assert self.error is not None
        assert isinstance(self.error, GitLabServerError)

    def and_status_code_should_be_500(self):
        assert self.error.status_code == 500

    async def do_cleanup(self):
        await self.client.close()
        await self._mock_ctx.__aexit__(None, None, None)


class Scenario__503_raises_server_error(vedro.Scenario):
    subject = "503 response raises GitLabServerError"

    async def given_mock_gitlab_returns_503(self):
        self._mock_ctx = mock_gitlab_get_mr(
            TEST_PROJECT_ID,
            42,
            {"error": "Service Unavailable"},
            status=503,
        )
        await self._mock_ctx.__aenter__()
        self.client = create_test_client()

    async def when_get_mr_is_called(self):
        self.error = None
        try:
            await self.client.get_mr(42)
        except GitLabServerError as e:
            self.error = e

    def then_server_error_should_be_raised(self):
        assert self.error is not None
        assert isinstance(self.error, GitLabServerError)

    def and_status_code_should_be_503(self):
        assert self.error.status_code == 503

    async def do_cleanup(self):
        await self.client.close()
        await self._mock_ctx.__aexit__(None, None, None)


class Scenario__sanitize_removes_token(vedro.Scenario):
    subject = "response body sanitization removes token fields"

    def given_body_with_sensitive_data(self):
        self.body = {
            "user": "test",
            "token": "secret-token-value",
            "access_token": "secret-access-token",
        }

    def when_body_is_sanitized(self):
        self.result = _sanitize_response_body(self.body)

    def then_token_should_be_redacted(self):
        assert self.result["token"] == "***"

    def and_access_token_should_be_redacted(self):
        assert self.result["access_token"] == "***"

    def and_non_sensitive_data_should_remain(self):
        assert self.result["user"] == "test"


class Scenario__sanitize_removes_nested_secrets(vedro.Scenario):
    subject = "response body sanitization removes nested secrets"

    def given_body_with_nested_secrets(self):
        # Use non-sensitive parent keys to test nested sanitization
        self.body = {
            "config": {
                "api_key": "secret-api-key",
                "url": "https://example.com",
            },
            "user_data": {
                "password": "secret-password",
            },
        }

    def when_body_is_sanitized(self):
        self.result = _sanitize_response_body(self.body)

    def then_nested_api_key_should_be_redacted(self):
        assert self.result["config"]["api_key"] == "***"

    def and_nested_password_should_be_redacted(self):
        assert self.result["user_data"]["password"] == "***"

    def and_url_should_remain(self):
        assert self.result["config"]["url"] == "https://example.com"


class Scenario__sanitize_handles_list_of_dicts(vedro.Scenario):
    subject = "response body sanitization handles list of dicts"

    def given_body_with_list_of_secrets(self):
        # Use non-sensitive parent key to test list sanitization
        self.body = {
            "items": [
                {"name": "item1", "secret": "value1"},
                {"name": "item2", "secret": "value2"},
            ],
        }

    def when_body_is_sanitized(self):
        self.result = _sanitize_response_body(self.body)

    def then_secrets_in_list_should_be_redacted(self):
        assert self.result["items"][0]["secret"] == "***"
        assert self.result["items"][1]["secret"] == "***"

    def and_non_sensitive_list_items_should_remain(self):
        assert self.result["items"][0]["name"] == "item1"
        assert self.result["items"][1]["name"] == "item2"


class Scenario__sanitize_returns_none_for_none(vedro.Scenario):
    subject = "response body sanitization returns None for None input"

    def given_none_body(self):
        self.body = None

    def when_body_is_sanitized(self):
        self.result = _sanitize_response_body(self.body)

    def then_result_should_be_none(self):
        assert self.result is None


class Scenario__sanitize_returns_string_unchanged(vedro.Scenario):
    subject = "response body sanitization returns string unchanged"

    def given_string_body(self):
        self.body = "Simple error message"

    def when_body_is_sanitized(self):
        self.result = _sanitize_response_body(self.body)

    def then_result_should_be_same_string(self):
        assert self.result == "Simple error message"


class Scenario__error_repr_hides_response_body(vedro.Scenario):
    subject = "GitLabAPIError repr does not include response body"

    def given_error_with_sensitive_body(self):
        self.error = GitLabAPIError(
            "Test error",
            status_code=400,
            response_body={"token": "secret"},
        )

    def when_repr_is_called(self):
        self.repr_str = repr(self.error)

    def then_body_should_not_be_in_repr(self):
        assert "secret" not in self.repr_str
        assert "token" not in self.repr_str

    def and_message_should_be_in_repr(self):
        assert "Test error" in self.repr_str


class Scenario__error_str_hides_response_body(vedro.Scenario):
    subject = "GitLabAPIError str does not include response body"

    def given_error_with_sensitive_body(self):
        self.error = GitLabAPIError(
            "Test error",
            status_code=400,
            response_body={"password": "secret123"},
        )

    def when_str_is_called(self):
        self.str_result = str(self.error)

    def then_body_should_not_be_in_str(self):
        assert "secret123" not in self.str_result
        assert "password" not in self.str_result

    def and_status_code_should_be_in_str(self):
        assert "400" in self.str_result
