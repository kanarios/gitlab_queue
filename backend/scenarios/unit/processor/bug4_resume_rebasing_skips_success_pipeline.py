"""BUG-4: Resume from rebasing skips SUCCESS pipeline because old_sha is empty."""

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

from ._helpers import create_processing_context, create_test_queue_item, instant_poll


class Scenario(vedro.Scenario):
    subject = "resume from rebasing calls _capture_pre_rebase_state"

    def given_processor_resuming_from_rebasing(self):
        self.gitlab_client = FakeGitLabClient()
        # First get_mr call (for _capture_pre_rebase_state) returns pre-rebase SHA
        # Subsequent calls return post-rebase SHA
        self.gitlab_client.mr_response_sequence = [
            create_mr(iid=42, sha="pre_rebase_sha_123", labels=["merge_queue"]),
        ]
        self.gitlab_client.mr_responses[42] = create_mr(
            iid=42,
            sha="new_sha_after_rebase",
            labels=["merge_queue"],
        )
        # Rebase is already complete (not in progress, no conflicts)
        self.gitlab_client.rebase_status = (False, False)
        # Pipeline with post-rebase SHA
        self.gitlab_client.latest_pipeline_response = create_pipeline(
            id=200,
            sha="new_sha_after_rebase",
            status="success",
        )

        self.queue_manager = FakeQueueManager()
        self.queue_manager.add_item(create_test_queue_item(mr_iid=42, state="rebasing"))

        self.sm = FakeStateMachine(current_state=FakeCurrentState(id="rebasing"))
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.sm)
        assert self.ctx.rebase_ctx.old_sha == "", "Precondition: old_sha should be empty"

        self.processor = MergeProcessor(
            gitlab_client=self.gitlab_client,
            queue_manager=self.queue_manager,
            notifier=FakeNotifier(),
            settings=FakeSettings(),
            poll_fn=instant_poll,
        )

    async def when_execute_workflow_is_called(self):
        self.result = await self.processor._execute_workflow(self.ctx)

    def then_old_sha_should_be_captured(self):
        assert self.ctx.rebase_ctx.old_sha == "pre_rebase_sha_123"

    def and_workflow_should_succeed(self):
        assert self.result == ProcessingResult.SUCCESS
