"""Test is_retryable_gitlab_error returns False for GitLabCircuitOpenError."""

from __future__ import annotations

import vedro

from gitlab_queue.utils.retry import is_retryable_gitlab_error

from .._helpers import create_circuit_open_error


class Scenario(vedro.Scenario):
    subject = "is_retryable_gitlab_error returns False for circuit open error"

    def given_circuit_open_error(self):
        """
        Create and store a GitLab circuit-open error on the test instance for use by subsequent steps.
        """
        self.error = create_circuit_open_error()

    def when_checked_for_retryability(self):
        """
        Check whether the previously prepared GitLab error is considered retryable and store the boolean outcome on self.result.
        """
        self.result = is_retryable_gitlab_error(self.error)

    def then_result_is_false(self):
        assert self.result is False
