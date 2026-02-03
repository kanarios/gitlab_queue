"""Test _process_iteration processes all events returned from the retry manager."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import vedro

from ._helpers import (
    create_test_retry_item,
    create_test_retry_processor,
)


class Scenario(vedro.Scenario):
    subject = "_process_iteration processes all events when multiple are returned"

    def given_processor_with_two_pending_events(self):
        self.processor = create_test_retry_processor()
        self.item1 = create_test_retry_item(id=1, event_type="merge_request")
        self.item2 = create_test_retry_item(id=2, event_type="merge_request")
        self.processor.retry_manager.get_events_ready_for_retry = AsyncMock(return_value=[self.item1, self.item2])

    async def when_process_iteration_is_called(self):
        with patch("gitlab_queue.webhooks.handlers.MRWebhookHandler") as mock_handler_cls:
            mock_handler_instance = AsyncMock()
            mock_handler_cls.return_value = mock_handler_instance
            await self.processor._process_iteration()

    def then_both_items_are_marked_success(self):
        assert self.processor.retry_manager.mark_retry_success.await_count == 2

    def and_success_called_for_first_item(self):
        calls = self.processor.retry_manager.mark_retry_success.await_args_list
        processed_ids = [call.args[0] for call in calls]
        assert self.item1.id in processed_ids

    def and_success_called_for_second_item(self):
        calls = self.processor.retry_manager.mark_retry_success.await_args_list
        processed_ids = [call.args[0] for call in calls]
        assert self.item2.id in processed_ids
