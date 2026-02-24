"""Test _process_retry_item marks failure when handler raises an exception."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import vedro

from ._helpers import create_test_retry_item, create_test_retry_processor


class Scenario(vedro.Scenario):
    subject = "_process_retry_item marks failure when handler raises exception"

    def given_processor_and_mr_item(self):
        self.processor = create_test_retry_processor()
        self.item = create_test_retry_item(event_type="merge_request")

    async def when_process_retry_item_is_called_and_handler_fails(self):
        with patch("gitlab_queue.webhooks.handlers.MRWebhookHandler") as mock_handler_cls:
            mock_handler_instance = AsyncMock()
            mock_handler_instance.handle.side_effect = RuntimeError("Handler failed")
            mock_handler_cls.return_value = mock_handler_instance
            await self.processor._process_retry_item(self.item)

    def then_mark_retry_failed_is_called(self):
        self.processor.retry_manager.mark_retry_failed.assert_awaited_once()

    def and_error_message_contains_failure_reason(self):
        call_args = self.processor.retry_manager.mark_retry_failed.call_args
        error_msg = call_args.args[1]
        assert "Handler failed" in error_msg

    def and_mark_retry_success_is_not_called(self):
        self.processor.retry_manager.mark_retry_success.assert_not_awaited()
