"""Test scenario: GitLabAPIError repr does not include response body."""

from __future__ import annotations

import vedro

from gitlab_queue.clients.gitlab import (
    GitLabAPIError,
)


class Scenario(vedro.Scenario):
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
