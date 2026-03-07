"""Test _process_retry_item marks success for merge request events."""

from __future__ import annotations

import vedro

from ._helpers import create_test_retry_item, create_test_retry_processor


class Scenario(vedro.Scenario):
    subject = "_process_retry_item marks success for merge request event"

    def given_processor_and_mr_retry_item(self):
        self.processor = create_test_retry_processor()
        self.item = create_test_retry_item(event_type="merge_request")

    async def when_process_retry_item_is_called(self):
        await self.processor._process_retry_item(self.item)

    def then_mark_retry_success_is_called(self):
        assert self.item.id in self.processor.retry_manager.success_calls

    def and_mark_retry_failed_is_not_called(self):
        assert self.processor.retry_manager.failed_calls == []
