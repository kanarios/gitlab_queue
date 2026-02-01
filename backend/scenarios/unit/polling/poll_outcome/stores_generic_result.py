"""Test PollOutcome supports generic type T for result."""

import vedro

from gitlab_queue.core.polling import PollOutcome


class Scenario(vedro.Scenario):
    subject = "PollOutcome supports generic type T for result"

    def given_dict_result_data(self):
        self.result_data = {"key": "value", "count": 42}

    def when_poll_outcome_is_created_with_result(self):
        self.outcome: PollOutcome[dict] = PollOutcome(
            completed=True,
            timed_out=False,
            shutdown_requested=False,
            result=self.result_data,
        )

    def then_result_contains_expected_data(self):
        assert self.outcome.result == self.result_data

    def and_result_key_is_accessible(self):
        assert self.outcome.result["key"] == "value"
