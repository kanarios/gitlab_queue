"""Test _process_retry_item marks failure for unknown event types."""

from __future__ import annotations

import vedro

from scenarios.fakes import FakeRetryManager

from ._helpers import create_test_retry_item, create_test_retry_processor


class Scenario(vedro.Scenario):
    subject = "_process_retry_item marks failure for unknown event type"

    def given_processor_and_item_with_unknown_event(self):
        self.retry_manager = FakeRetryManager()
        self.processor = create_test_retry_processor(
            retry_manager=self.retry_manager,
            event_parser=lambda payload: None,
        )
        self.item = create_test_retry_item(
            event_type="unknown",
            payload={"object_kind": "unknown_kind"},
        )

    async def when_process_retry_item_is_called(self):
        await self.processor._process_retry_item(self.item)

    def then_mark_retry_failed_is_called(self):
        assert len(self.retry_manager.failed_calls) == 1

    def and_error_message_mentions_unknown(self):
        error_msg = self.retry_manager.failed_calls[0]["error_message"]
        assert "Unknown event type" in error_msg

    def and_mark_retry_success_is_not_called(self):
        assert self.retry_manager.success_calls == []
