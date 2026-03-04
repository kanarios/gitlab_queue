"""Test run() logs generic exceptions and continues the loop.

Lines 212-214: generic Exception handler catches errors without stopping the loop.
Lines 217-218: normal sleep after successful iteration is cancellable.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import vedro

from .._helpers import create_mock_processor


class Scenario(vedro.Scenario):
    subject = "run logs generic exception and continues loop until sleep interrupted"

    def given_processor_that_raises_generic_exception_then_succeeds(self):
        self.processor = create_mock_processor()
        self.call_count = 0

        async def process_iteration_side_effect():
            self.call_count += 1
            if self.call_count == 1:
                raise RuntimeError("some unexpected error")
            # Second iteration: succeed

        self.process_iteration_side_effect = process_iteration_side_effect

        async def interruptible_sleep_side_effect(_seconds):
            # Normal sleep after iteration — shut down
            self.processor._shutdown_event.set()
            return False

        self.interruptible_sleep_side_effect = interruptible_sleep_side_effect

    async def when_run_is_called(self):
        with (
            patch.object(self.processor, "_recover_interrupted_state", new_callable=AsyncMock),
            patch.object(self.processor, "_sync_missing_mrs_from_gitlab", new_callable=AsyncMock),
            patch.object(
                self.processor,
                "_process_iteration",
                new_callable=AsyncMock,
                side_effect=self.process_iteration_side_effect,
            ),
            patch.object(
                self.processor,
                "_interruptible_sleep",
                new_callable=AsyncMock,
                side_effect=self.interruptible_sleep_side_effect,
            ) as self.mock_sleep,
        ):
            await self.processor.run()

    def then_process_iteration_was_called_once(self):
        # Exception occurs → sleep is called → returns False → break
        # So _process_iteration is only called once
        assert self.call_count == 1

    def and_interruptible_sleep_was_called_after_exception(self):
        self.mock_sleep.assert_called_once()
