"""Test is_retryable_sqlite_error returns False for IntegrityError."""

from __future__ import annotations

import vedro

from gitlab_queue.utils.retry import is_retryable_sqlite_error

from .._helpers import create_integrity_error


class Scenario(vedro.Scenario):
    subject = "is_retryable_sqlite_error returns False for integrity error"

    def given_integrity_error(self):
        self.error = create_integrity_error()

    def when_checked_for_retryability(self):
        self.result = is_retryable_sqlite_error(self.error)

    def then_result_is_false(self):
        assert self.result is False
