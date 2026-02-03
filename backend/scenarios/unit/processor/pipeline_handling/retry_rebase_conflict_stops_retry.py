"""Test _handle_pipeline_failure_retry stops when rebase raises GitLabConflictError.

When a pipeline fails and retry is attempted, but the rebase operation
raises a GitLabConflictError due to merge conflicts, the retry should
stop and trigger_pipeline_failed should be called on the state machine.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import vedro

from gitlab_queue.clients.gitlab import GitLabConflictError

from .._helpers import (
    create_mock_mr,
    create_mock_pipeline,
    create_mock_processor,
    create_mock_state_machine,
    create_processing_context,
    create_test_queue_item,
)


class Scenario(vedro.Scenario):
    subject = "pipeline failure retry stops on rebase conflict error"

    def given_processor_with_rebase_raising_conflict(self):
        self.processor = create_mock_processor()

        self.queue_item = create_test_queue_item(mr_iid=42, state="testing", expected_sha="abc123")
        self.processor.queue_manager.get_queue_item.return_value = self.queue_item

        self.pipeline = create_mock_pipeline(pipeline_id=100, sha="abc123", status="failed")

        # _capture_pre_rebase_sha calls get_mr
        self.mock_mr = create_mock_mr(iid=42, sha="abc123")
        self.processor.gitlab_client.get_mr.return_value = self.mock_mr

        # Rebase raises conflict error
        self.processor.gitlab_client.rebase_mr = AsyncMock(side_effect=GitLabConflictError("Merge conflict"))

        self.mock_sm = create_mock_state_machine()
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.mock_sm)

        self.retry_count = 0
        self.max_retries = 1
        self.failed_jobs = ["unit_tests"]

    async def when_handle_pipeline_failure_retry_is_called(self):
        self.should_continue, self.new_start_time = await self.processor._handle_pipeline_failure_retry(
            ctx=self.ctx,
            pipeline=self.pipeline,
            failed_jobs=self.failed_jobs,
            retry_count=self.retry_count,
            max_retries=self.max_retries,
        )

    def then_should_continue_is_false(self):
        assert self.should_continue is False

    def and_new_start_time_is_none(self):
        assert self.new_start_time is None

    def and_pipeline_failed_was_triggered(self):
        self.mock_sm.trigger_pipeline_failed.assert_called_once()
