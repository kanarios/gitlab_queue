"""Test _calculate_duration returns hours format for durations 3600s+."""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import vedro
from vedro import params

from .._helpers import MockQueueItem, create_state_machine


class Scenario(vedro.Scenario):
    subject = "_calculate_duration returns '{expected}' for {seconds} seconds"

    @params(3600, "1h 0m")
    @params(7320, "2h 2m")
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
        with patch("gitlab_queue.core.state_machine.datetime") as mock_datetime:
            mock_datetime.now.return_value = self.fixed_now
            self.result = self.sm._calculate_duration(self.queue_item)

    def then_result_matches_expected_format(self):
        assert self.result == self.expected
