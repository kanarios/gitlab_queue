"""Test _process_iteration stops processing events when shutdown is set mid-batch."""

from __future__ import annotations

import vedro

from scenarios.fakes import FakeHandler, FakeHandlerFactory, FakeRetryManager

from ._helpers import (
    create_test_retry_item,
    create_test_retry_processor,
)


class Scenario(vedro.Scenario):
    subject = "_process_iteration stops mid-batch when shutdown is requested"

    def given_processor_with_two_events_and_shutdown_after_first(self):
        self.item1 = create_test_retry_item(item_id=1, event_type="merge_request")
        self.item2 = create_test_retry_item(item_id=2, event_type="merge_request")
        self.retry_manager = FakeRetryManager(_ready_events=[self.item1, self.item2])

        self.handler = FakeHandler()
        self.processor = create_test_retry_processor(
            retry_manager=self.retry_manager,
            mr_handler_factory=FakeHandlerFactory(handler=self.handler),
        )

        original_process = self.processor._process_retry_item

        async def process_and_shutdown(item):
            await original_process(item)
            self.processor._shutdown_event.set()

        self.processor._process_retry_item = process_and_shutdown

    async def when_process_iteration_is_called(self):
        await self.processor._process_iteration()

    def then_only_first_item_is_marked_success(self):
        assert len(self.retry_manager.success_calls) == 1

    def and_first_item_was_processed(self):
        assert self.retry_manager.success_calls[0] == self.item1.id

    def and_shutdown_is_set(self):
        assert self.processor.is_shutdown_requested is True
