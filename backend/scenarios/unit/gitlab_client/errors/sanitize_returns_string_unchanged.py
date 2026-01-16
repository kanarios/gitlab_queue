"""Test scenario: response body sanitization returns string unchanged."""

from __future__ import annotations

import vedro

from gitlab_queue.clients.gitlab import (
    _sanitize_response_body,
)


class Scenario(vedro.Scenario):
    subject = "response body sanitization returns string unchanged"

    def given_string_body(self):
        self.body = "Simple error message"

    def when_body_is_sanitized(self):
        self.result = _sanitize_response_body(self.body)

    def then_result_should_be_same_string(self):
        assert self.result == "Simple error message"
