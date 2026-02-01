"""Test PollOutcome default result is None."""

import vedro

from gitlab_queue.core.polling import PollOutcome


class Scenario(vedro.Scenario):
    subject = "PollOutcome default result is None"

    def given_poll_outcome_without_result(self):
        self.outcome = PollOutcome(
            completed=True,
            timed_out=False,
            shutdown_requested=False,
        )

    def then_result_is_none(self):
        assert self.outcome.result is None
