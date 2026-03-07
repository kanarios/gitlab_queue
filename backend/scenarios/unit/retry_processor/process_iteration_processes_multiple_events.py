"""Test _process_iteration processes all events returned from the retry manager."""

from __future__ import annotations

import vedro

from scenarios.fakes import FakeRetryManager

from ._helpers import (
    create_test_retry_item,
    create_test_retry_processor,
)


class Scenario(vedro.Scenario):
    subject = "_process_iteration processes all events when multiple are returned"

    def given_processor_with_two_pending_events(self):
        self.item1 = create_test_retry_item(item_id=1, event_type="merge_request")
        self.item2 = create_test_retry_item(item_id=2, event_type="merge_request")
        self.retry_manager = FakeRetryManager(_ready_events=[self.item1, self.item2])
        self.processor = create_test_retry_processor(retry_manager=self.retry_manager)

    async def when_process_iteration_is_called(self):
        await self.processor._process_iteration()

    def then_both_items_are_marked_success(self):
        assert len(self.retry_manager.success_calls) == 2

    def and_success_called_for_first_item(self):
        assert self.item1.id in self.retry_manager.success_calls

    def and_success_called_for_second_item(self):
        assert self.item2.id in self.retry_manager.success_calls
