"""Test _process_retry_item marks failure for a parsed but unsupported event type."""

from __future__ import annotations

import vedro

from scenarios.fakes import FakeRetryManager

from ._helpers import create_test_retry_item, create_test_retry_processor


class _UnknownEvent:
    """A custom event type that is neither MergeRequestEvent nor PipelineEvent."""


class Scenario(vedro.Scenario):
    subject = "_process_retry_item marks failure for unsupported parsed event type"

    def given_processor_and_item_with_unsupported_event(self):
        self.retry_manager = FakeRetryManager()
        self.unsupported_event = _UnknownEvent()
        self.processor = create_test_retry_processor(
            retry_manager=self.retry_manager,
            event_parser=lambda payload: self.unsupported_event,
        )
        self.item = create_test_retry_item(event_type="merge_request")

    async def when_process_retry_item_is_called(self):
        await self.processor._process_retry_item(self.item)

    def then_mark_retry_failed_is_called(self):
        assert len(self.retry_manager.failed_calls) == 1

    def and_error_message_mentions_unsupported(self):
        error_msg = self.retry_manager.failed_calls[0]["error_message"]
        assert "Unsupported event type" in error_msg

    def and_mark_retry_success_is_not_called(self):
        assert self.retry_manager.success_calls == []
