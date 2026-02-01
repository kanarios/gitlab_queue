"""Test PollOutcome stores boolean flags correctly."""

import vedro
from vedro import params

from gitlab_queue.core.polling import PollOutcome


class Scenario(vedro.Scenario):
    subject = "PollOutcome stores {field}={value}"

    @params("completed", True)
    @params("completed", False)
    @params("timed_out", True)
    @params("timed_out", False)
    @params("shutdown_requested", True)
    @params("shutdown_requested", False)
    def __init__(self, field: str, value: bool):
        self.field = field
        self.value = value

    def given_kwargs_with_flag_set(self):
        self.kwargs = {
            "completed": False,
            "timed_out": False,
            "shutdown_requested": False,
        }
        self.kwargs[self.field] = self.value

    def when_poll_outcome_is_created(self):
        self.outcome = PollOutcome(**self.kwargs)

    def then_field_has_expected_value(self):
        assert getattr(self.outcome, self.field) == self.value
