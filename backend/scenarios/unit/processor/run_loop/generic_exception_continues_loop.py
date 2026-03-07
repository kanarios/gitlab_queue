"""Test run() logs generic exceptions and continues the loop.

When _process_iteration raises a generic Exception, run() should log it
and continue to the next iteration rather than stopping.
"""

from __future__ import annotations

import vedro

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
            raise RuntimeError("some unexpected error")

    async def _interruptible_sleep(self, seconds: float) -> bool:
        self.sleep_calls.append(seconds)
        if len(self.sleep_calls) >= 2:
            self._shutdown_event.set()
            return False
        return True


class Scenario(vedro.Scenario):
    subject = "run logs generic exception and continues loop until sleep interrupted"

    def given_processor_that_raises_generic_exception_then_succeeds(self):
        base = create_mock_processor()
        self.processor = _TestableProcessor(
            gitlab_client=base.gitlab_client,
            queue_manager=base.queue_manager,
            notifier=base.notifier,
            settings=base.settings,
        )

    async def when_run_is_called(self):
        await self.processor.run()

    def then_process_iteration_was_called_twice(self):
        assert self.processor.iteration_count == 2

    def and_interruptible_sleep_was_called_twice(self):
        assert len(self.processor.sleep_calls) == 2
