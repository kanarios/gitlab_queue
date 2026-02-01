"""Test PollStatus enum values match expected strings."""

import vedro
from vedro import params

from gitlab_queue.core.polling import PollStatus


class Scenario(vedro.Scenario):
    subject = "PollStatus.{name} has value '{expected}'"

    @params("CONTINUE", "continue")
    @params("DONE", "done")
    def __init__(self, name: str, expected: str):
        self.name = name
        self.expected = expected

    def given_poll_status_enum(self):
        self.status = getattr(PollStatus, self.name)

    def then_value_matches_expected(self):
        assert self.status.value == self.expected
