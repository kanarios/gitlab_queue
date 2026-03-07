"""Test log_after_retry executes without raising when multiple attempts succeeded."""

from __future__ import annotations

import vedro

from gitlab_queue.utils.retry import log_after_retry
from scenarios.fakes import FakeOutcome, FakeRetryCallState


class Scenario(vedro.Scenario):
    subject = "log_after_retry logs on success after retry without raising"

    def given_retry_call_state_with_successful_outcome_after_retry(self):
        self.state = FakeRetryCallState(
            outcome=FakeOutcome(_exception=None, failed=False),
            seconds_since_start=1.5,
            attempt_number=2,
        )

    def when_log_after_retry_is_called(self):
        self.raised = None
        try:
            log_after_retry(self.state)
        except Exception as exc:
            self.raised = exc

    def then_no_exception_was_raised(self):
        assert self.raised is None
