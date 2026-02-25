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
        """
        Prepare a mock processor whose _process_iteration raises a GitLabCircuitOpenError on first call and signals shutdown on the second.
        
        Sets up:
        - self.processor: a mock processor instance from create_mock_processor().
        - self.call_count: a counter starting at 0.
        - self.process_iteration_side_effect: an async side effect that increments the counter, raises GitLabCircuitOpenError(retry_after=1) when called the first time, and sets self.processor._shutdown_event on the second call to stop the run loop.
        """
        self.processor = create_mock_processor()

        self.call_count = 0

        async def process_iteration_side_effect():
            """
            Side effect for tests that simulates a GitLab circuit-breaker opening on the first call and stops the processor on the next call.
            
            Increments `self.call_count`. On the first invocation raises `GitLabCircuitOpenError(retry_after=1)`; on the second invocation sets `self.processor._shutdown_event` to signal shutdown.
            """
            self.call_count += 1
            if self.call_count == 1:
                raise GitLabCircuitOpenError(retry_after=1)
            # Second call: let it pass, shutdown will stop the loop
            self.processor._shutdown_event.set()

        self.process_iteration_side_effect = process_iteration_side_effect

    async def when_run_is_called(self):
        """
        Starts the processor run loop with key internals patched to simulate a circuit-open error and controlled sleep behavior.
        
        Patches:
        - _recover_interrupted_state and _sync_missing_mrs_from_gitlab as no-op AsyncMocks.
        - _process_iteration as an AsyncMock using self.process_iteration_side_effect to raise GitLabCircuitOpenError on the first iteration and signal shutdown afterwards.
        - _interruptible_sleep as an AsyncMock with side effect self._interruptible_sleep_side_effect; the mock is exposed as self.mock_sleep.
        
        Awaits self.processor.run() so the scenario exercises the processor's handling of a circuit-breaker open condition and verifies sleep was invoked with the expected retry interval.
        """
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
        """
        Signal shutdown and act as a test side effect for an interruptible sleep.
        
        Sets the processor's shutdown event to stop the run loop, then returns `False`.
        
        Parameters:
            seconds (int | float): Requested sleep duration (unused by the side effect).
        
        Returns:
            bool: `False` indicating the sleep was interrupted or did not complete.
        """
        self.processor._shutdown_event.set()
        return False

    def then_interruptible_sleep_was_called(self):
        """
        Asserts that the interruptible sleep was awaited with the GitLab circuit's retry_after value of 1 second.
        
        Verifies that the mocked _interruptible_sleep was awaited with an argument of 1.
        """
        self.mock_sleep.assert_any_await(1)
