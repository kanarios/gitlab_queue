"""Test scenario: response body sanitization removes token fields."""

from __future__ import annotations

import vedro

from gitlab_queue.clients.gitlab import (
    _sanitize_response_body,
)


class Scenario(vedro.Scenario):
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
