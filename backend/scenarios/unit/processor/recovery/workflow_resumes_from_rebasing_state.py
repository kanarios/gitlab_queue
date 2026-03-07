"""Test _execute_workflow resumes from rebasing state.

When the processor finds an MR with current_state "rebasing", it should
capture the pre-rebase SHA, then proceed through rebase wait, pipeline,
and merge steps. This test configures fakes so the full workflow succeeds.
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
    create_pipeline,
)

from .._helpers import create_processing_context, create_test_queue_item, instant_poll


class Scenario(vedro.Scenario):
    subject = "execute workflow resumes from rebasing state"

    def given_processor_with_mr_in_rebasing_state(self):
        self.gitlab_client = FakeGitLabClient()
        # First get_mr (for _capture_pre_rebase_state) returns pre-rebase SHA
        self.gitlab_client.mr_response_sequence = [
            create_mr(iid=42, sha="old_sha", labels=["merge_queue"]),
        ]
        # Subsequent get_mr calls return post-rebase SHA
        self.gitlab_client.mr_responses[42] = create_mr(
            iid=42,
            sha="new_sha",
            labels=["merge_queue"],
        )
        # Rebase is already complete
        self.gitlab_client.rebase_status = (False, False)
        # Pipeline with post-rebase SHA and success status
        self.gitlab_client.latest_pipeline_response = create_pipeline(
            id=200,
            sha="new_sha",
            status="success",
        )

        self.queue_manager = FakeQueueManager()
        self.queue_manager.add_item(create_test_queue_item(mr_iid=42, state="rebasing"))

        self.sm = FakeStateMachine(current_state=FakeCurrentState(id="rebasing"))
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.sm)

        self.processor = MergeProcessor(
            gitlab_client=self.gitlab_client,
            queue_manager=self.queue_manager,
            notifier=FakeNotifier(),
            settings=FakeSettings(),
            poll_fn=instant_poll,
        )

    async def when_execute_workflow_is_called(self):
        self.result = await self.processor._execute_workflow(self.ctx)

    def then_result_is_success(self):
        assert self.result == ProcessingResult.SUCCESS

    def and_rebase_complete_was_triggered(self):
        assert len(self.sm.rebase_complete_calls) == 1
