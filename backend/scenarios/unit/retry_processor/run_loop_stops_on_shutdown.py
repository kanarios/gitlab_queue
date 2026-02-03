"""Test run() exits immediately when shutdown event is already set."""

from __future__ import annotations

import vedro

from ._helpers import create_test_retry_processor


class Scenario(vedro.Scenario):
    subject = "run() exits immediately when shutdown is already requested"

    def given_processor_with_shutdown_already_set(self):
        self.processor = create_test_retry_processor()
        self.processor._shutdown_event.set()

    async def when_run_is_called(self):
        await self.processor.run()

    def then_run_completes_without_processing(self):
        self.processor.retry_manager.get_events_ready_for_retry.assert_not_awaited()

    def and_shutdown_is_still_set(self):
        assert self.processor.is_shutdown_requested is True
