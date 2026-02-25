"""Test _handle_pipeline_failure_retry when create_pipeline raises GitLabAPIError.

When the retry rebase succeeds but no auto-created pipeline is found with
matching ID, the processor attempts to force-create a pipeline. If that
create_pipeline call raises GitLabAPIError, the retry should fail and
return (False, None).
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import vedro

from gitlab_queue.clients.gitlab import GitLabAPIError

from .._helpers import (
    create_mock_mr,
    create_mock_pipeline,
    create_mock_processor,
    create_mock_state_machine,
    create_processing_context,
    create_test_queue_item,
)


class Scenario(vedro.Scenario):
    subject = "pipeline failure retry fails when force create pipeline raises api error"

    def given_processor_with_create_pipeline_failing(self):
        """
        Prepare a mock processor and context where forcing a pipeline creation fails with a GitLabAPIError.
        
        Configures:
        - a test queue item (mr_iid=42) and an old failed pipeline (id=100, sha="sha_old");
        - gitlab client to report rebase complete and to return an MR with sha "sha_new";
        - get_latest_mr_pipeline to return the old pipeline (no new auto-created pipeline);
        - create_pipeline to raise GitLabAPIError("Pipeline creation failed");
        - notifier.build_pipeline_url to format pipeline URLs;
        - a mock state machine and processing context for mr_iid=42;
        - retry parameters: retry_count=0, max_retries=1, and failed_jobs=["test_job"].
        """
        self.processor = create_mock_processor()

        self.queue_item = create_test_queue_item(mr_iid=42, state="testing", expected_sha="sha_old")
        self.processor.queue_manager.get_queue_item.return_value = self.queue_item

        self.old_pipeline = create_mock_pipeline(pipeline_id=100, sha="sha_old", status="failed")

        # Rebase completes immediately
        self.processor.gitlab_client.check_rebase_status = AsyncMock(return_value=(False, False))

        # MR after rebase has new SHA
        self.mock_mr = create_mock_mr(iid=42, sha="sha_new")
        self.mock_mr.source_branch = "feature/mr-42"
        self.mock_mr.rebase_in_progress = False
        self.processor.gitlab_client.get_mr.return_value = self.mock_mr

        # _wait_for_post_rebase_pipeline returns the same pipeline
        # (simulates no new auto-created pipeline found, same old id)
        self.processor.gitlab_client.get_latest_mr_pipeline = AsyncMock(return_value=self.old_pipeline)

        # Force-create pipeline raises API error
        self.processor.gitlab_client.create_pipeline = AsyncMock(side_effect=GitLabAPIError("Pipeline creation failed"))

        self.processor.notifier.build_pipeline_url.side_effect = lambda pid: f"https://gitlab.com/pipeline/{pid}"

        self.mock_sm = create_mock_state_machine()
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.mock_sm)

        self.retry_count = 0
        self.max_retries = 1
        self.failed_jobs = ["test_job"]

    async def when_handle_pipeline_failure_retry_is_called(self):
        self.should_continue, self.new_start_time = await self.processor._handle_pipeline_failure_retry(
            ctx=self.ctx,
            pipeline=self.old_pipeline,
            failed_jobs=self.failed_jobs,
            retry_count=self.retry_count,
            max_retries=self.max_retries,
        )

    def then_should_continue_is_false(self):
        assert self.should_continue is False

    def and_new_start_time_is_none(self):
        assert self.new_start_time is None
