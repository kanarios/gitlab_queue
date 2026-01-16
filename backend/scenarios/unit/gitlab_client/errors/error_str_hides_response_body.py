"""Test scenario: GitLabAPIError str does not include response body."""

from __future__ import annotations

import vedro

from gitlab_queue.clients.gitlab import (
    GitLabAPIError,
)


class Scenario(vedro.Scenario):
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
