"""Test log_before_retry executes without raising given a valid RetryCallState."""

from __future__ import annotations

import vedro

from gitlab_queue.clients.gitlab import GitLabServerError
from gitlab_queue.utils.retry import log_before_retry
from scenarios.fakes import FakeNextAction, FakeOutcome, FakeRetryCallState


class Scenario(vedro.Scenario):
    subject = "log_before_retry logs attempt info without raising"

    def given_retry_call_state_with_failed_outcome(self):
        self.state = FakeRetryCallState(
            outcome=FakeOutcome(
                _exception=GitLabServerError("Internal Server Error", status_code=500),
                failed=True,
            ),
            next_action=FakeNextAction(sleep=1.0),
            seconds_since_start=0.5,
            attempt_number=2,
        )

    def when_log_before_retry_is_called(self):
        self.raised = None
        try:
            log_before_retry(self.state)
        except Exception as exc:
            self.raised = exc

    def then_no_exception_was_raised(self):
        assert self.raised is None
