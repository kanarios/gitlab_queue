"""Test _process_retry_item marks failure for unknown event types."""

from __future__ import annotations

from unittest.mock import patch

import vedro

from ._helpers import create_test_retry_item, create_test_retry_processor


class Scenario(vedro.Scenario):
    subject = "_process_retry_item marks failure for unknown event type"

    def given_processor_and_item_with_unknown_event(self):
        self.processor = create_test_retry_processor()
        self.item = create_test_retry_item(
            event_type="unknown",
            payload={"object_kind": "unknown_kind"},
        )

    async def when_process_retry_item_is_called(self):
        with patch(
            "gitlab_queue.webhooks.retry_processor.parse_webhook_event",
            return_value=None,
        ):
            await self.processor._process_retry_item(self.item)

    def then_mark_retry_failed_is_called(self):
        self.processor.retry_manager.mark_retry_failed.assert_awaited_once()

    def and_error_message_mentions_unknown(self):
        call_args = self.processor.retry_manager.mark_retry_failed.call_args
        error_msg = call_args.args[1]
        assert "Unknown event type" in error_msg

    def and_mark_retry_success_is_not_called(self):
        self.processor.retry_manager.mark_retry_success.assert_not_awaited()
