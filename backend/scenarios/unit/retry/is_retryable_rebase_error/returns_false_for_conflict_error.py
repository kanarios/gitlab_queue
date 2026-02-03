"""Test _is_retryable_rebase_error returns False for GitLabConflictError."""

from __future__ import annotations

import vedro

from gitlab_queue.clients.gitlab import GitLabConflictError
from gitlab_queue.utils.retry import _is_retryable_rebase_error


class Scenario(vedro.Scenario):
    subject = "_is_retryable_rebase_error returns False for GitLabConflictError"

    def given_conflict_error(self):
        self.error = GitLabConflictError("Merge conflict", status_code=409)

    def when_checked_for_retryability(self):
        self.result = _is_retryable_rebase_error(self.error)

    def then_result_is_false(self):
        assert self.result is False
