"""Test _process_retry_item moves event to DLQ when max retries exceeded."""

from __future__ import annotations

import vedro

from scenarios.fakes import FakeHandler, FakeHandlerFactory

from ._helpers import create_fake_retry_manager, create_test_retry_item, create_test_retry_processor


class Scenario(vedro.Scenario):
    subject = "_process_retry_item logs DLQ warning when event is moved to dead letter queue"

    def given_processor_and_item_at_max_retries(self):
        self.retry_manager = create_fake_retry_manager(_dlq_on_fail=True)
        self.handler = FakeHandler(handle_error=RuntimeError("max retries exceeded"))
        self.processor = create_test_retry_processor(
            retry_manager=self.retry_manager,
            mr_handler_factory=FakeHandlerFactory(handler=self.handler),
        )
        self.item = create_test_retry_item(
            event_type="merge_request",
            attempt_count=2,
        )

    async def when_process_retry_item_is_called_and_handler_raises(self):
        await self.processor._process_retry_item(self.item)

    def then_mark_retry_failed_is_called(self):
        assert len(self.retry_manager.failed_calls) == 1

    def and_mark_retry_failed_returns_true(self):
        assert self.retry_manager._dlq_on_fail is True

    def and_mark_retry_success_is_not_called(self):
        assert self.retry_manager.success_calls == []
