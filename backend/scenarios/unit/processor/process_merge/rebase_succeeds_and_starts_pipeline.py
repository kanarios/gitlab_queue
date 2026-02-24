"""Test _handle_pipeline_failure_retry when retry count has not been exhausted.

When a pipeline fails and the retry count is below the maximum, the processor
should attempt a rebase, wait for a new pipeline, and signal the caller to
continue polling with an updated retry count.

Covers lines 612-650: retry path in _handle_pipeline_failure_retry where
rebase succeeds and a new pipeline is found.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import vedro

from .._helpers import (
    create_mock_pipeline,
    create_mock_processor,
    create_mock_state_machine,
    create_processing_context,
    create_test_queue_item,
)


class Scenario(vedro.Scenario):
    subject = "handle pipeline failure retry returns retry signal when new pipeline found"

    def given_processor_with_failed_pipeline_and_retry_available(self):
        self.processor = create_mock_processor()

        # Queue item carries the expected SHA for the MR
        self.queue_item = create_test_queue_item(mr_iid=42, state="testing", expected_sha="sha_old")
        self.processor.queue_manager.get_queue_item.return_value = self.queue_item

        # Old pipeline (the one that failed)
        self.old_pipeline = create_mock_pipeline(pipeline_id=100, sha="sha_old", status="failed")

        # New pipeline returned after the retry rebase - different id, updated sha
        self.new_pipeline = create_mock_pipeline(pipeline_id=200, sha="sha_new", status="running")

        # Rebase completes immediately (not in progress, no conflicts)
        self.processor.gitlab_client.check_rebase_status = AsyncMock(return_value=(False, False))

        # _capture_pre_rebase_sha calls get_mr (returns pre-rebase SHA),
        # then _wait_for_post_rebase_pipeline calls get_mr again (returns post-rebase SHA).
        mock_mr_before = MagicMock()
        mock_mr_before.sha = "sha_old"
        mock_mr_before.rebase_in_progress = False
        mock_mr_before.source_branch = "feature/mr-42"

        mock_mr_after = MagicMock()
        mock_mr_after.sha = "sha_new"
        mock_mr_after.rebase_in_progress = False
        mock_mr_after.source_branch = "feature/mr-42"

        self.processor.gitlab_client.get_mr = AsyncMock(
            side_effect=[mock_mr_before, mock_mr_after, mock_mr_after]
        )

        self.processor.gitlab_client.get_latest_mr_pipeline = AsyncMock(return_value=self.new_pipeline)
        self.processor.notifier.build_pipeline_url.side_effect = lambda pid: f"https://gitlab.com/pipeline/{pid}"

        self.mock_sm = create_mock_state_machine()
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.mock_sm)

        self.failed_jobs = ["test_job"]
        self.retry_count = 0
        self.max_retries = 1

    async def when_handle_pipeline_failure_retry_is_called(self):
        self.should_continue, self.new_start_time = await self.processor._handle_pipeline_failure_retry(
            ctx=self.ctx,
            pipeline=self.old_pipeline,
            failed_jobs=self.failed_jobs,
            retry_count=self.retry_count,
            max_retries=self.max_retries,
        )

    def then_should_continue_is_true(self):
        assert self.should_continue is True

    def and_new_start_time_is_set(self):
        assert self.new_start_time is not None
        assert isinstance(self.new_start_time, datetime)

    def and_pipeline_retry_is_notified_on_state_machine(self):
        self.mock_sm.notify_pipeline_retry.assert_awaited_once()
        call_kwargs = self.mock_sm.notify_pipeline_retry.call_args.kwargs
        assert call_kwargs["old_pipeline_id"] == 100
        assert call_kwargs["new_pipeline_id"] == 200
        assert call_kwargs["retry_count"] == 1
        assert call_kwargs["max_retries"] == 1

    def and_pipeline_failed_is_not_triggered(self):
        self.mock_sm.trigger_pipeline_failed.assert_not_awaited()
