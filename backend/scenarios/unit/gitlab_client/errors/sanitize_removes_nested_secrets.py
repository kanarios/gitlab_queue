"""Test scenario: response body sanitization removes nested secrets."""

from __future__ import annotations

import vedro

from gitlab_queue.clients.gitlab import (
    _sanitize_response_body,
)


class Scenario(vedro.Scenario):
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
