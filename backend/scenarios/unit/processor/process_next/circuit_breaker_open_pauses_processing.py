"""Test run() handles GitLabCircuitOpenError by pausing processing.

When _process_iteration raises GitLabCircuitOpenError, the processor
should pause via _interruptible_sleep with the retry_after value,
rather than crashing or stopping entirely.
"""

from __future__ import annotations

import vedro

from gitlab_queue.clients.gitlab import GitLabCircuitOpenError
from gitlab_queue.core.processor import MergeProcessor
from scenarios.fakes import FakeGitLabClient, FakeNotifier, FakeQueueManager, FakeSettings


class Scenario(vedro.Scenario):
    subject = "run pauses processing when circuit breaker is open"

    def given_processor_with_circuit_open_error(self):
        self.queue_manager = FakeQueueManager(
            get_next_mr_sequence=[
                GitLabCircuitOpenError(retry_after=1),
            ],
        )

        self.sleep_durations: list[float] = []

        async def recording_sleep(seconds: float) -> bool:
            self.sleep_durations.append(seconds)
            return False  # Signal shutdown to stop the loop

        self.processor = MergeProcessor(
            gitlab_client=FakeGitLabClient(),
            queue_manager=self.queue_manager,
            notifier=FakeNotifier(),
            settings=FakeSettings(),
            sleep_fn=recording_sleep,
        )

    async def when_run_is_called(self):
        await self.processor.run()

    def then_sleep_was_called_with_retry_after(self):
        assert self.sleep_durations[0] == 1
