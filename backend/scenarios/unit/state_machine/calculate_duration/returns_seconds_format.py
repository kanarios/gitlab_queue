"""Test _calculate_duration returns seconds format for durations under 60s."""

from datetime import UTC, datetime, timedelta

import vedro
from vedro import params

from .._helpers import MockQueueItem, create_state_machine


class Scenario(vedro.Scenario):
    subject = "_calculate_duration returns '{expected}' for {seconds} seconds"

    @params(0, "0s")
    @params(30, "30s")
    @params(59, "59s")
    def __init__(self, seconds: int, expected: str):
        self.seconds = seconds
        self.expected = expected

    def given_state_machine_and_queue_item(self):
        self.sm = create_state_machine()
        self.fixed_now = datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC)
        self.queue_item = MockQueueItem(
            queued_at=self.fixed_now - timedelta(seconds=self.seconds),
        )

    def when_calculate_duration_is_called(self):
        self.result = self.sm._calculate_duration(self.queue_item, now=self.fixed_now)

    def then_result_matches_expected_format(self):
        assert self.result == self.expected
