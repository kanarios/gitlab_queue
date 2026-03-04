"""Test wait_for_shutdown() returns False when timeout expires before shutdown.

Lines 1549-1550: wait_for_shutdown() returns False on timeout.
"""

from __future__ import annotations

import vedro

from .._helpers import create_mock_processor


class Scenario(vedro.Scenario):
    subject = "wait_for_shutdown returns False when timeout expires"

    def given_processor_without_shutdown(self):
        self.processor = create_mock_processor()

    async def when_wait_for_shutdown_times_out(self):
        self.result = await self.processor.wait_for_shutdown(timeout=0.01)

    def then_result_is_false(self):
        assert self.result is False
