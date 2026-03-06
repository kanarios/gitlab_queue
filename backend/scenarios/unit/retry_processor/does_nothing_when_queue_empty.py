"""Test _process_iteration does nothing when retry queue is empty."""

from __future__ import annotations

import vedro

from ._helpers import create_test_retry_processor


class Scenario(vedro.Scenario):
    subject = "_process_iteration does nothing when queue is empty"

    def given_processor_with_empty_queue(self):
        self.processor = create_test_retry_processor()

    async def when_process_iteration_is_called(self):
        await self.processor._process_iteration()

    def then_mark_retry_success_is_not_called(self):
        assert self.processor.retry_manager.success_calls == []

    def and_mark_retry_failed_is_not_called(self):
        assert self.processor.retry_manager.failed_calls == []
