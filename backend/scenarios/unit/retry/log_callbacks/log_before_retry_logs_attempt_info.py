"""Test log_before_retry executes without raising given a valid RetryCallState."""

from __future__ import annotations

from unittest.mock import MagicMock

import vedro

from gitlab_queue.clients.gitlab import GitLabServerError
from gitlab_queue.utils.retry import log_before_retry


class Scenario(vedro.Scenario):
    subject = "log_before_retry logs attempt info without raising"

    def given_retry_call_state_with_failed_outcome(self):
        self.state = MagicMock()
        self.state.outcome = MagicMock()
        self.state.outcome.exception.return_value = GitLabServerError("Internal Server Error", status_code=500)
        self.state.outcome.failed = True
        self.state.next_action = MagicMock()
        self.state.next_action.sleep = 1.0
        self.state.seconds_since_start = 0.5
        self.state.attempt_number = 2

    def when_log_before_retry_is_called(self):
        self.raised = None
        try:
            log_before_retry(self.state)
        except Exception as exc:
            self.raised = exc

    def then_no_exception_was_raised(self):
        assert self.raised is None
