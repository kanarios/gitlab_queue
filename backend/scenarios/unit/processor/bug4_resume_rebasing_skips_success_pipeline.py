"""BUG-4: Resume from rebasing skips SUCCESS pipeline because old_sha is empty."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import vedro

from gitlab_queue.core.processor import ProcessingResult

from ._helpers import (
    create_mock_gitlab_client,
    create_mock_notifier,
    create_mock_queue_manager,
    create_mock_settings,
    create_mock_state_machine,
    create_processing_context,
)


class Scenario(vedro.Scenario):
    subject = "resume from rebasing calls _capture_pre_rebase_sha"

    def given_processor_resuming_from_rebasing(self):
        self.gitlab_client = create_mock_gitlab_client()
        self.queue_manager = create_mock_queue_manager()
        self.notifier = create_mock_notifier()
        self.settings = create_mock_settings()

        # State machine starts in "rebasing"
        self.sm = create_mock_state_machine()
        self.sm.current_state.id = "rebasing"

        self.ctx = create_processing_context(mr_iid=42, state_machine=self.sm)
        # Simulate empty old_sha (bug condition)
        assert self.ctx.rebase_ctx.old_sha == "", "Precondition: old_sha should be empty"

        from gitlab_queue.core.processor import MergeProcessor

        self.processor = MergeProcessor(
            gitlab_client=self.gitlab_client,
            queue_manager=self.queue_manager,
            notifier=self.notifier,
            settings=self.settings,
        )

        # Mock get_mr to return MR with sha
        mr_mock = MagicMock()
        mr_mock.sha = "pre_rebase_sha_123"
        self.gitlab_client.get_mr = AsyncMock(return_value=mr_mock)

        # Mock _wait_for_rebase to succeed
        self.processor._wait_for_rebase = AsyncMock(return_value=ProcessingResult.SUCCESS)
        # Mock _wait_for_pipeline to succeed
        self.processor._wait_for_pipeline = AsyncMock(return_value=ProcessingResult.SUCCESS)
        # Mock _process_merge to succeed
        self.processor._process_merge = AsyncMock(return_value=ProcessingResult.SUCCESS)

    async def when_execute_workflow_is_called(self):
        self.result = await self.processor._execute_workflow(self.ctx)

    def then_old_sha_should_be_captured(self):
        assert self.ctx.rebase_ctx.old_sha != "", "Expected old_sha to be captured, got empty string"

    def and_workflow_should_succeed(self):
        assert self.result == ProcessingResult.SUCCESS
