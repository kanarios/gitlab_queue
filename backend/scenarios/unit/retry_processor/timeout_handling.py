"""Test timeout handling in retry processor.

Covers retry_processor.py lines 80-87, 236-237, 259-260:
- run loop catches exceptions in _process_iteration
- _interruptible_sleep returns True on timeout (sleep completes)
- wait_for_shutdown returns False on timeout
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import vedro

from ._helpers import create_test_retry_processor


class Scenario(vedro.Scenario):
    subject = "run loop catches exception in _process_iteration and continues"

    def given_processor_with_failing_iteration(self):
        self.processor = create_test_retry_processor()
        self.processor.retry_manager.get_events_ready_for_retry = AsyncMock(
            side_effect=RuntimeError("Database connection lost"),
        )
        # Make the processor shut down after one iteration
        self._iteration_count = 0

        original_sleep = self.processor._interruptible_sleep

        async def mock_sleep(seconds):
            self._iteration_count += 1
            if self._iteration_count >= 1:
                self.processor.request_shutdown()
            return False

        self.processor._interruptible_sleep = mock_sleep

    async def when_run_is_called(self):
        self.raised = False
        try:
            await self.processor.run()
        except Exception:
            self.raised = True

    def then_no_exception_is_propagated(self):
        assert self.raised is False

    def and_shutdown_was_requested(self):
        assert self.processor.is_shutdown_requested is True


class Scenario2(vedro.Scenario):
    subject = "_interruptible_sleep returns True when sleep completes without interruption"

    def given_processor_without_shutdown(self):
        self.processor = create_test_retry_processor()

    async def when_interruptible_sleep_is_called_with_tiny_timeout(self):
        self.result = await self.processor._interruptible_sleep(0.01)

    def then_result_is_true(self):
        assert self.result is True


class Scenario3(vedro.Scenario):
    subject = "wait_for_shutdown returns False on timeout"

    def given_processor_without_shutdown_requested(self):
        self.processor = create_test_retry_processor()

    async def when_wait_for_shutdown_is_called_with_tiny_timeout(self):
        self.result = await self.processor.wait_for_shutdown(timeout=0.01)

    def then_result_is_false(self):
        assert self.result is False


class Scenario4(vedro.Scenario):
    subject = "wait_for_shutdown returns True when shutdown is already requested"

    def given_processor_with_shutdown_requested(self):
        self.processor = create_test_retry_processor()
        self.processor.request_shutdown()

    async def when_wait_for_shutdown_is_called(self):
        self.result = await self.processor.wait_for_shutdown(timeout=1.0)

    def then_result_is_true(self):
        assert self.result is True
