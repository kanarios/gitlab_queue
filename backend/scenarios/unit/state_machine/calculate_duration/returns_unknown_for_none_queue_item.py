"""Test _calculate_duration returns 'unknown' for None queue_item."""

import vedro

from .._helpers import create_state_machine


class Scenario(vedro.Scenario):
    subject = "_calculate_duration returns 'unknown' for None queue_item"

    def given_state_machine(self):
        self.sm = create_state_machine()

    def when_calculate_duration_is_called_with_none(self):
        self.result = self.sm._calculate_duration(None)

    def then_result_is_unknown(self):
        assert self.result == "unknown"
