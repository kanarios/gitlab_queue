"""Test _wait_for_pipeline continues polling when no pipeline is found.

When get_latest_mr_pipeline returns None, the pipeline wait loop should
continue polling rather than terminating. A short timeout causes the loop
to exit, proving it continued polling multiple times.
"""

from __future__ import annotations

import vedro

from gitlab_queue.core.processor import MergeProcessor, ProcessingResult
from scenarios.fakes import (
    FakeCurrentState,
    FakeGitLabClient,
    FakeNotifier,
    FakeQueueManager,
    FakeSettings,
    FakeStateMachine,
    create_mr,
)

from .._helpers import create_processing_context, create_test_queue_item


class Scenario(vedro.Scenario):
    subject = "wait for pipeline continues polling when no pipeline found"

    def given_processor_with_no_pipeline(self):
        self.gitlab_client = FakeGitLabClient()
        self.gitlab_client.mr_responses[42] = create_mr(
            iid=42,
            labels=["merge_queue"],
        )
        # latest_pipeline_response=None by default — no pipeline found

        self.queue_manager = FakeQueueManager()
        self.queue_manager.add_item(create_test_queue_item(mr_iid=42, state="testing"))

        self.processor = MergeProcessor(
            gitlab_client=self.gitlab_client,
            queue_manager=self.queue_manager,
            notifier=FakeNotifier(),
            settings=FakeSettings(
                pipeline_timeout_seconds=0.5,
                pipeline_poll_interval_seconds=0.01,
            ),
        )

        self.sm = FakeStateMachine(current_state=FakeCurrentState(id="testing"))
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.sm)

    async def when_wait_for_pipeline_is_called(self):
        self.result = await self.processor._wait_for_pipeline(self.ctx)

    def then_result_indicates_timeout(self):
        assert self.result == ProcessingResult.TIMEOUT

    def and_pipeline_was_polled_multiple_times(self):
        assert len(self.gitlab_client.get_latest_pipeline_calls) >= 2
