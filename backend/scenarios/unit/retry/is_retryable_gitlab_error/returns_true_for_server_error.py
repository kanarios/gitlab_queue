"""Test is_retryable_gitlab_error returns True for GitLabServerError."""

from __future__ import annotations

import vedro

from gitlab_queue.utils.retry import is_retryable_gitlab_error

from .._helpers import create_server_error


class Scenario(vedro.Scenario):
    subject = "is_retryable_gitlab_error returns True for server error"

    def given_server_error(self):
        self.error = create_server_error()

    def when_checked_for_retryability(self):
        self.result = is_retryable_gitlab_error(self.error)

    def then_result_is_true(self):
        assert self.result is True
