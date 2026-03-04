"""Test _interruptible_sleep returns True when sleep completes without shutdown.

Lines 1292-1294: when shutdown event is NOT set during sleep, asyncio.wait_for raises
TimeoutError (sleep completed normally) and _interruptible_sleep returns True.
"""

from __future__ import annotations

import vedro

from .._helpers import create_mock_processor


class Scenario(vedro.Scenario):
    subject = "interruptible_sleep returns True when sleep completes normally"

    def given_processor_without_shutdown(self):
        self.processor = create_mock_processor()
        # Shutdown event is NOT set — sleep will complete normally

    async def when_interruptible_sleep_is_called_with_short_timeout(self):
        # Very short sleep (1ms) — TimeoutError will be raised → returns True
        self.result = await self.processor._interruptible_sleep(0.001)

    def then_result_is_true(self):
        assert self.result is True
