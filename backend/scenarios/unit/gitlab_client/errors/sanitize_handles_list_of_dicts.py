"""Test scenario: response body sanitization handles list of dicts."""

from __future__ import annotations

import vedro

from gitlab_queue.clients.gitlab import (
    _sanitize_response_body,
)


class Scenario(vedro.Scenario):
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
