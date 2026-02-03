"""Test _process_retry_item logs DLQ warning when mark_retry_failed returns True."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import vedro

from ._helpers import create_test_retry_item, create_test_retry_processor


class Scenario(vedro.Scenario):
    subject = "_process_retry_item logs DLQ warning when event is moved to dead letter queue"

    def given_processor_and_item_at_max_retries(self):
        self.processor = create_test_retry_processor()
        self.item = create_test_retry_item(
            event_type="merge_request",
            attempt_count=2,
        )
        # mark_retry_failed returns True to indicate the event was moved to DLQ
        self.processor.retry_manager.mark_retry_failed = AsyncMock(return_value=True)

    async def when_process_retry_item_is_called_and_handler_raises(self):
        with patch("gitlab_queue.webhooks.handlers.MRWebhookHandler") as mock_handler_cls:
            mock_handler_instance = AsyncMock()
            mock_handler_instance.handle.side_effect = RuntimeError("max retries exceeded")
            mock_handler_cls.return_value = mock_handler_instance
            await self.processor._process_retry_item(self.item)

    def then_mark_retry_failed_is_called(self):
        self.processor.retry_manager.mark_retry_failed.assert_awaited_once()

    def and_mark_retry_failed_returns_true(self):
        result = self.processor.retry_manager.mark_retry_failed.return_value
        assert result is True

    def and_mark_retry_success_is_not_called(self):
        self.processor.retry_manager.mark_retry_success.assert_not_awaited()
