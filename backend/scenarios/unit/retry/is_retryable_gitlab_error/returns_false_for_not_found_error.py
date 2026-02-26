"""Test is_retryable_gitlab_error returns False for GitLabNotFoundError."""

from __future__ import annotations

import vedro

from gitlab_queue.utils.retry import is_retryable_gitlab_error

from .._helpers import create_not_found_error


class Scenario(vedro.Scenario):
    subject = "is_retryable_gitlab_error returns False for not found error"

    def given_not_found_error(self):
        """
        Create and store a GitLab "not found" error for the scenario.

        Assigns the error object returned by create_not_found_error() to self.error.
        """
        self.error = create_not_found_error()

    def when_checked_for_retryability(self):
        """
        Checks whether the stored GitLab error is considered retryable and stores the boolean outcome on self.result.

        This step calls is_retryable_gitlab_error with the error previously set on the scenario and records the result as a boolean attribute.
        """
        self.result = is_retryable_gitlab_error(self.error)

    def then_result_is_false(self):
        """
        Asserts that the previously stored result is False.
        """
        assert self.result is False
