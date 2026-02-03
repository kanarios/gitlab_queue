"""Test is_retryable_gitlab_error returns False for GitLabNotFoundError."""

from __future__ import annotations

import vedro

from gitlab_queue.utils.retry import is_retryable_gitlab_error

from .._helpers import create_not_found_error


class Scenario(vedro.Scenario):
    subject = "is_retryable_gitlab_error returns False for not found error"

    def given_not_found_error(self):
        self.error = create_not_found_error()

    def when_checked_for_retryability(self):
        self.result = is_retryable_gitlab_error(self.error)

    def then_result_is_false(self):
        assert self.result is False
