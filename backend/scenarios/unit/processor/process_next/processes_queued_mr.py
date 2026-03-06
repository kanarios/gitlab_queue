"""Test _process_iteration picks up and processes a queued MR.

When get_next_mr returns a queue item, the processor should call _process_mr
with that item, creating a state machine for it and clearing _current_mr_iid after.
"""

from __future__ import annotations

import vedro

from gitlab_queue.core.processor import MergeProcessor
from scenarios.fakes import (
    FakeGitLabClient,
    FakeNotifier,
    FakeQueueManager,
    FakeSettings,
    FakeStateMachineFactory,
    create_mr,
)

from .._helpers import create_test_queue_item


class Scenario(vedro.Scenario):
    subject = "process iteration calls process mr for queued item"

    def given_processor_with_mr_in_queue(self):
        self.queue_item = create_test_queue_item(mr_iid=42, state="queued", stale_warning_sent=True)

        self.gitlab_client = FakeGitLabClient()
        # MR without queue label so _verify_mr_in_queue returns False
        # and _process_mr exits quickly with REMOVED
        self.gitlab_client.mr_responses[42] = create_mr(
            iid=42,
            labels=[],
        )

        self.queue_manager = FakeQueueManager()
        self.queue_manager.add_item(self.queue_item)

        self.sm_factory = FakeStateMachineFactory()
        self.processor = MergeProcessor(
            gitlab_client=self.gitlab_client,
            queue_manager=self.queue_manager,
            notifier=FakeNotifier(),
            settings=FakeSettings(),
            state_machine_factory=self.sm_factory,
        )

    async def when_process_iteration_is_called(self):
        await self.processor._process_iteration()

    def then_state_machine_was_created_for_the_item(self):
        assert len(self.sm_factory.calls) == 1
        assert self.sm_factory.calls[0]["mr_iid"] == 42

    def and_current_mr_iid_is_cleared_after_processing(self):
        assert self.processor._current_mr_iid is None
