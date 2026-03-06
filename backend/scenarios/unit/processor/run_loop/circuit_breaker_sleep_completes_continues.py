"""Test run() continues loop when circuit breaker sleep completes without interrupt.

When _interruptible_sleep returns True after a GitLabCircuitOpenError,
run() skips the regular sleep and proceeds to the next iteration.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import vedro

from gitlab_queue.clients.gitlab import GitLabCircuitOpenError

from .._helpers import create_mock_processor


class Scenario(vedro.Scenario):
    subject = "run continues loop after circuit breaker sleep completes normally"

    def given_processor_with_circuit_breaker_then_normal_iteration(self):
        self.processor = create_mock_processor()
        self.call_count = 0
        self.sleep_call_count = 0

        async def process_iteration_side_effect():
            self.call_count += 1
            if self.call_count == 1:
                raise GitLabCircuitOpenError(retry_after=2)
            # Second iteration: succeed silently, then the normal sleep will exit

        self.process_iteration_side_effect = process_iteration_side_effect

        async def interruptible_sleep_side_effect(seconds):  # noqa: ARG001
            self.sleep_call_count += 1
            if self.sleep_call_count == 1:
                # First sleep: circuit breaker wait — completes normally (True)
                return True
            # Second sleep: normal poll interval — set shutdown and return False
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

    def then_circuit_breaker_sleep_was_called_with_retry_after(self):
        self.mock_sleep.assert_any_await(2)

    def and_process_iteration_was_called_twice(self):
        assert self.call_count == 2

    def and_sleep_was_called_twice_total(self):
        assert self.sleep_call_count == 2
