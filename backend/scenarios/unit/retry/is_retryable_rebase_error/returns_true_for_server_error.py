"""Test _is_retryable_rebase_error returns True for GitLabServerError."""

from __future__ import annotations

import vedro

from gitlab_queue.clients.gitlab import GitLabServerError
from gitlab_queue.utils.retry import _is_retryable_rebase_error


class Scenario(vedro.Scenario):
    subject = "_is_retryable_rebase_error returns True for GitLabServerError"

    def given_server_error(self):
        self.error = GitLabServerError("Internal Server Error", status_code=500)

    def when_checked_for_retryability(self):
        self.result = _is_retryable_rebase_error(self.error)

    def then_result_is_true(self):
        assert self.result is True
