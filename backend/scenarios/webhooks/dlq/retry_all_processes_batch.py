"""Test that retry processor _process_iteration processes a batch of retry items.

When the retry processor runs an iteration, it fetches a batch of events ready
for retry and processes each one sequentially. This test verifies that all
items in the batch are processed and marked as successful.
Covers the batch processing logic in retry_processor._process_iteration.
"""

from __future__ import annotations

import vedro
from scenarios.fakes import FakeRetryManager
from scenarios.unit.retry_processor._helpers import (
    create_test_retry_item,
    create_test_retry_processor,
)


class Scenario(vedro.Scenario):
    subject = "retry processor processes a batch of DLQ retry items"

    def given_processor_with_multiple_retry_items(self):
        self.item1 = create_test_retry_item(item_id=1, event_type="merge_request")
        self.item2 = create_test_retry_item(item_id=2, event_type="pipeline")
        self.item3 = create_test_retry_item(item_id=3, event_type="merge_request")
        self.retry_manager = FakeRetryManager(
            _ready_events=[self.item1, self.item2, self.item3],
        )
        self.processor = create_test_retry_processor(retry_manager=self.retry_manager)

    async def when_process_iteration_is_called(self):
        await self.processor._process_iteration()

    def then_all_three_items_should_be_marked_as_success(self):
        assert len(self.retry_manager.success_calls) == 3

    def and_each_item_id_should_be_marked(self):
        assert 1 in self.retry_manager.success_calls
        assert 2 in self.retry_manager.success_calls
        assert 3 in self.retry_manager.success_calls

    def and_no_items_should_be_marked_as_failed(self):
        assert self.retry_manager.failed_calls == []
