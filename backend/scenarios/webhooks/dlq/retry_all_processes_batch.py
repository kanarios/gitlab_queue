"""Test that retry processor _process_iteration processes a batch of retry items.

When the retry processor runs an iteration, it fetches a batch of events ready
for retry and processes each one sequentially. This test verifies that all
items in the batch are processed and marked as successful.
Covers the batch processing logic in retry_processor._process_iteration.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import vedro
from scenarios.unit.retry_processor._helpers import (
    create_test_retry_item,
    create_test_retry_processor,
)


class Scenario(vedro.Scenario):
    subject = "retry processor processes a batch of DLQ retry items"

    def given_processor_with_multiple_retry_items(self):
        self.processor = create_test_retry_processor()
        self.item1 = create_test_retry_item(id=1, event_type="merge_request")
        self.item2 = create_test_retry_item(id=2, event_type="pipeline")
        self.item3 = create_test_retry_item(id=3, event_type="merge_request")
        self.processor.retry_manager.get_events_ready_for_retry = AsyncMock(
            return_value=[self.item1, self.item2, self.item3]
        )

    async def when_process_iteration_is_called(self):
        with (
            patch("gitlab_queue.webhooks.handlers.MRWebhookHandler") as mock_mr_handler_cls,
            patch("gitlab_queue.webhooks.handlers.PipelineWebhookHandler") as mock_pipeline_handler_cls,
        ):
            mock_mr_handler_instance = AsyncMock()
            mock_mr_handler_cls.return_value = mock_mr_handler_instance
            mock_pipeline_handler_instance = AsyncMock()
            mock_pipeline_handler_cls.return_value = mock_pipeline_handler_instance
            await self.processor._process_iteration()

    def then_all_three_items_should_be_marked_as_success(self):
        assert self.processor.retry_manager.mark_retry_success.await_count == 3

    def and_each_item_id_should_be_marked(self):
        marked_ids = [call.args[0] for call in self.processor.retry_manager.mark_retry_success.await_args_list]
        assert 1 in marked_ids
        assert 2 in marked_ids
        assert 3 in marked_ids

    def and_no_items_should_be_marked_as_failed(self):
        self.processor.retry_manager.mark_retry_failed.assert_not_awaited()
