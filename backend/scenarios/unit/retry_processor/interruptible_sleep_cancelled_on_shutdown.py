"""Test _interruptible_sleep returns False when shutdown is requested."""

from __future__ import annotations

import vedro

from ._helpers import create_test_retry_processor


class Scenario(vedro.Scenario):
    subject = "_interruptible_sleep returns False when shutdown is already set"

    def given_processor_with_shutdown_requested(self):
        self.processor = create_test_retry_processor()
        self.processor.request_shutdown()

    async def when_interruptible_sleep_is_called(self):
        self.result = await self.processor._interruptible_sleep(1)

    def then_result_is_false(self):
        assert self.result is False
