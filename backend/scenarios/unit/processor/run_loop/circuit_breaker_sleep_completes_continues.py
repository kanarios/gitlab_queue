"""Test run() continues loop when circuit breaker sleep completes without interrupt.

When _interruptible_sleep returns True after a GitLabCircuitOpenError,
run() skips the regular sleep and proceeds to the next iteration.
"""

from __future__ import annotations

import vedro

from gitlab_queue.clients.gitlab import GitLabCircuitOpenError
from gitlab_queue.core.processor import MergeProcessor

from .._helpers import create_mock_processor


class _TestableProcessor(MergeProcessor):
    """Subclass that overrides internal methods for testing the run loop."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.iteration_count = 0
        self.sleep_calls: list[float] = []

    async def _recover_interrupted_state(self) -> None:
        pass

    async def _sync_missing_mrs_from_gitlab(self) -> None:
        pass

    async def _process_iteration(self) -> None:
        self.iteration_count += 1
        if self.iteration_count == 1:
            raise GitLabCircuitOpenError(retry_after=2)

    async def _interruptible_sleep(self, seconds: float) -> bool:
        self.sleep_calls.append(seconds)
        if len(self.sleep_calls) == 1:
            return True  # circuit breaker sleep completes normally
        self._shutdown_event.set()
        return False  # normal poll interval — trigger shutdown


class Scenario(vedro.Scenario):
    subject = "run continues loop after circuit breaker sleep completes normally"

    def given_processor_with_circuit_breaker_then_normal_iteration(self):
        base = create_mock_processor()
        self.processor = _TestableProcessor(
            gitlab_client=base.gitlab_client,
            queue_manager=base.queue_manager,
            notifier=base.notifier,
            settings=base.settings,
        )

    async def when_run_is_called(self):
        await self.processor.run()

    def then_circuit_breaker_sleep_was_called_with_retry_after(self):
        assert 2 in self.processor.sleep_calls

    def and_process_iteration_was_called_twice(self):
        assert self.processor.iteration_count == 2

    def and_sleep_was_called_twice_total(self):
        assert len(self.processor.sleep_calls) == 2
