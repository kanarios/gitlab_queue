"""Test _calculate_duration returns 'unknown' for None queued_at."""

import vedro

from .._helpers import MockQueueItem, create_state_machine


class Scenario(vedro.Scenario):
    subject = "_calculate_duration returns 'unknown' for None queued_at"

    def given_state_machine_and_queue_item_without_queued_at(self):
        self.sm = create_state_machine()
        self.queue_item = MockQueueItem(queued_at=None)

    def when_calculate_duration_is_called(self):
        self.result = self.sm._calculate_duration(self.queue_item)

    def then_result_is_unknown(self):
        assert self.result == "unknown"
