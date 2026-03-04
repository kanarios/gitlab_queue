"""Test _interruptible_sleep returns False when shutdown event is set.

Lines 1285-1294: _interruptible_sleep returns False when event fires during wait.
"""

from __future__ import annotations

import vedro

from .._helpers import create_mock_processor


class Scenario(vedro.Scenario):
    subject = "interruptible_sleep returns False when shutdown is requested"

    def given_processor_with_shutdown_event_set(self):
        self.processor = create_mock_processor()
        self.processor._shutdown_event.set()

    async def when_interruptible_sleep_is_called(self):
        self.result = await self.processor._interruptible_sleep(60.0)

    def then_result_is_false(self):
        assert self.result is False
