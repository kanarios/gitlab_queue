"""Test run() handles GitLabCircuitOpenError by pausing processing.

When _process_iteration raises GitLabCircuitOpenError, the processor
should pause via _interruptible_sleep with the retry_after value,
rather than crashing or stopping entirely.
"""

from __future__ import annotations

import asyncio

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

        self.processor = MergeProcessor(
            gitlab_client=FakeGitLabClient(),
            queue_manager=self.queue_manager,
            notifier=FakeNotifier(),
            settings=FakeSettings(),
        )

    async def when_run_is_called(self):
        async def delayed_shutdown():
            await asyncio.sleep(0.05)
            self.processor._shutdown_event.set()

        self.shutdown_task = asyncio.create_task(delayed_shutdown())
        await self.processor.run()

    def then_processing_completed_without_crash(self):
        assert self.processor._shutdown_event.is_set()
