"""Test _calculate_duration returns hours format for durations 3600s+."""

import vedro
from vedro import params

from .._helpers import create_queue_item_with_age, create_state_machine


class Scenario(vedro.Scenario):
    subject = "_calculate_duration returns '{expected}' for {seconds} seconds"

    @params(3600, "1h 0m")
    @params(7320, "2h 2m")
    def __init__(self, seconds: int, expected: str):
        self.seconds = seconds
        self.expected = expected

    def given_state_machine_and_queue_item(self):
        self.sm = create_state_machine()
        self.queue_item = create_queue_item_with_age(self.seconds)

    def when_calculate_duration_is_called(self):
        self.result = self.sm._calculate_duration(self.queue_item)

    def then_result_matches_expected_format(self):
        assert self.result == self.expected
