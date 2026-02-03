"""Test _process_iteration stops processing events when shutdown is set mid-batch."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import vedro

from ._helpers import (
    create_test_retry_item,
    create_test_retry_processor,
)


class Scenario(vedro.Scenario):
    subject = "_process_iteration stops mid-batch when shutdown is requested"

    def given_processor_with_two_events_and_shutdown_after_first(self):
        self.processor = create_test_retry_processor()
        self.item1 = create_test_retry_item(id=1, event_type="merge_request")
        self.item2 = create_test_retry_item(id=2, event_type="merge_request")
        self.processor.retry_manager.get_events_ready_for_retry = AsyncMock(return_value=[self.item1, self.item2])

        original_process = self.processor._process_retry_item

        async def process_and_shutdown(item):
            await original_process(item)
            # Signal shutdown after processing the first item
            self.processor._shutdown_event.set()

        self.processor._process_retry_item = process_and_shutdown

    async def when_process_iteration_is_called(self):
        with patch("gitlab_queue.webhooks.handlers.MRWebhookHandler") as mock_handler_cls:
            mock_handler_instance = AsyncMock()
            mock_handler_cls.return_value = mock_handler_instance
            await self.processor._process_iteration()

    def then_only_first_item_is_marked_success(self):
        assert self.processor.retry_manager.mark_retry_success.await_count == 1

    def and_first_item_was_processed(self):
        call_args = self.processor.retry_manager.mark_retry_success.call_args
        assert call_args.args[0] == self.item1.id

    def and_shutdown_is_set(self):
        assert self.processor.is_shutdown_requested is True
