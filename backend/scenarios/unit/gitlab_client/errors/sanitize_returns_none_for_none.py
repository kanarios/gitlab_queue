"""Test scenario: response body sanitization returns None for None input."""

from __future__ import annotations

import vedro

from gitlab_queue.clients.gitlab import (
    _sanitize_response_body,
)


class Scenario(vedro.Scenario):
    subject = "response body sanitization returns None for None input"

    def given_none_body(self):
        self.body = None

    def when_body_is_sanitized(self):
        self.result = _sanitize_response_body(self.body)

    def then_result_should_be_none(self):
        assert self.result is None
