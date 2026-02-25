"""Test run() handles GitLabCircuitOpenError by pausing processing.

When _process_iteration raises GitLabCircuitOpenError, the processor
should call _interruptible_sleep with the retry_after value to pause
before the next iteration, rather than crashing or stopping entirely.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import vedro

from gitlab_queue.clients.gitlab import GitLabCircuitOpenError

from .._helpers import create_mock_processor


class Scenario(vedro.Scenario):
    subject = "run pauses processing when circuit breaker is open"

    def given_processor_with_circuit_open_error(self):
        self.processor = create_mock_processor()

        self.call_count = 0

        async def process_iteration_side_effect():
            self.call_count += 1
            if self.call_count == 1:
                raise GitLabCircuitOpenError(retry_after=1)
            # Second call: let it pass, shutdown will stop the loop
            self.processor._shutdown_event.set()

        self.process_iteration_side_effect = process_iteration_side_effect

    async def when_run_is_called(self):
        with (
            patch.object(
                self.processor,
                "_recover_interrupted_state",
                new_callable=AsyncMock,
            ),
            patch.object(
                self.processor,
                "_sync_missing_mrs_from_gitlab",
                new_callable=AsyncMock,
            ),
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
                side_effect=self._interruptible_sleep_side_effect,
            ) as self.mock_sleep,
        ):
            await self.processor.run()

    async def _interruptible_sleep_side_effect(self, seconds):
        # After first sleep (circuit breaker), set shutdown to stop loop
        self.processor._shutdown_event.set()
        return False

    def then_interruptible_sleep_was_called(self):
        self.mock_sleep.assert_any_await(1)
