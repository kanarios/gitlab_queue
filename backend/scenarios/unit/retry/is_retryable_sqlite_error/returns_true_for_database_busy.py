"""Test is_retryable_sqlite_error returns True for 'busy' error."""

from __future__ import annotations

import vedro

from gitlab_queue.utils.retry import is_retryable_sqlite_error

from .._helpers import create_db_busy_error


class Scenario(vedro.Scenario):
    subject = "is_retryable_sqlite_error returns True for database busy error"

    def given_database_busy_error(self):
        self.error = create_db_busy_error()

    def when_checked_for_retryability(self):
        self.result = is_retryable_sqlite_error(self.error)

    def then_result_is_true(self):
        assert self.result is True
