"""Test is_retryable_gitlab_error returns True for GitLabRateLimitError."""

from __future__ import annotations

import vedro

from gitlab_queue.utils.retry import is_retryable_gitlab_error

from .._helpers import create_rate_limit_error


class Scenario(vedro.Scenario):
    subject = "is_retryable_gitlab_error returns True for rate limit error"

    def given_rate_limit_error(self):
        self.error = create_rate_limit_error()

    def when_checked_for_retryability(self):
        self.result = is_retryable_gitlab_error(self.error)

    def then_result_is_true(self):
        assert self.result is True
