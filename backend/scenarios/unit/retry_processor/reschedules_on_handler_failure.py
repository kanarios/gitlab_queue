"""Test _process_retry_item marks failure when handler raises an exception."""

from __future__ import annotations

import vedro

from scenarios.fakes import FakeHandler, FakeHandlerFactory

from ._helpers import create_fake_retry_manager, create_test_retry_item, create_test_retry_processor


class Scenario(vedro.Scenario):
    subject = "_process_retry_item marks failure when handler raises exception"

    def given_processor_and_mr_item(self):
        self.retry_manager = create_fake_retry_manager()
        self.handler = FakeHandler(handle_error=RuntimeError("Handler failed"))
        self.processor = create_test_retry_processor(
            retry_manager=self.retry_manager,
            mr_handler_factory=FakeHandlerFactory(handler=self.handler),
        )
        self.item = create_test_retry_item(event_type="merge_request")

    async def when_process_retry_item_is_called_and_handler_fails(self):
        await self.processor._process_retry_item(self.item)

    def then_mark_retry_failed_is_called(self):
        assert len(self.retry_manager.failed_calls) == 1

    def and_error_message_contains_failure_reason(self):
        error_msg = self.retry_manager.failed_calls[0]["error_message"]
        assert "Handler failed" in error_msg

    def and_mark_retry_success_is_not_called(self):
        assert self.retry_manager.success_calls == []
