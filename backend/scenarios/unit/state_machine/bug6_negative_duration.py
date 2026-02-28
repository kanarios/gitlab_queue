"""Test: _calculate_duration clamps negative duration to 0s."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import vedro

from ._helpers import MockQueueItem, create_state_machine


class Scenario(vedro.Scenario):
    subject = "_calculate_duration returns '0s' when queued_at is in the future"

    def given_state_machine_and_future_queue_item(self):
        self.sm = create_state_machine()
        self.queue_item = MockQueueItem(
            queued_at=datetime.now(UTC) + timedelta(hours=1),
        )

    def when_duration_is_calculated(self):
        self.result = self.sm._calculate_duration(self.queue_item)

    def then_result_should_be_zero_seconds(self):
        assert self.result == "0s"
