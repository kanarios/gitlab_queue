"""Test wait_for_shutdown returns True when shutdown event is already set."""

from __future__ import annotations

import vedro

from ._helpers import create_test_retry_processor


class Scenario(vedro.Scenario):
    subject = "wait_for_shutdown returns True when shutdown event is already set"

    def given_processor_with_shutdown_already_set(self):
        self.processor = create_test_retry_processor()
        self.processor._shutdown_event.set()

    async def when_wait_for_shutdown_is_called_with_timeout(self):
        self.result = await self.processor.wait_for_shutdown(timeout=5.0)

    def then_result_is_true(self):
        assert self.result is True
