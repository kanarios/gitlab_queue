"""Test _handle_pipeline_failure_retry stops when rebase raises GitLabConflictError.

When a pipeline fails and retry is attempted, but the rebase operation
raises a GitLabConflictError due to merge conflicts, the retry should
stop and trigger_pipeline_failed should be called on the state machine.
"""

from __future__ import annotations

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
        """
        Set up a mock processor and test context where a rebase operation raises GitLabConflictError.
        """
        self.processor = create_mock_processor()

        self.queue_item = create_test_queue_item(mr_iid=42, state="testing", expected_sha="abc123")
        self.processor.queue_manager.add_item(self.queue_item)

        self.pipeline = create_mock_pipeline(pipeline_id=100, sha="abc123", status="failed")

        # _capture_pre_rebase_sha calls get_mr
        self.mock_mr = create_mock_mr(iid=42, sha="abc123")
        self.processor.gitlab_client.mr_responses[42] = self.mock_mr

        # Rebase raises conflict error
        self.processor.gitlab_client.rebase_mr_error = GitLabConflictError("Merge conflict")

        self.mock_sm = create_mock_state_machine()
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.mock_sm)

        self.retry_count = 0
        self.max_retries = 1
        self.failed_jobs = ["unit_tests"]

    async def when_handle_pipeline_failure_retry_is_called(self):
        """
        Invokes the processor's pipeline-failure retry handler and captures its decision and next start time.

        Sets self.should_continue to `True` if retrying should proceed, otherwise `False`; sets self.new_start_time to the next retry start time or `None`.
        """
        self.should_continue, self.new_start_time = await self.processor._handle_pipeline_failure_retry(
            ctx=self.ctx,
            pipeline=self.pipeline,
            failed_jobs=self.failed_jobs,
            retry_count=self.retry_count,
            max_retries=self.max_retries,
        )

    def then_should_continue_is_false(self):
        """
        Asserts that the retry handling stopped by verifying `should_continue` is False.

        This test expectation fails if `should_continue` is not `False`.
        """
        assert self.should_continue is False

    def and_new_start_time_is_none(self):
        """
        Asserts that the retry handler did not produce a new start time.

        Raises an AssertionError if `self.new_start_time` is not None.
        """
        assert self.new_start_time is None

    def and_pipeline_failed_was_triggered(self):
        """
        Asserts that the scenario's state machine had its `trigger_pipeline_failed` method awaited exactly once.

        This verifies the processor signaled a pipeline-failure transition to the state machine.
        """
        assert len(self.mock_sm.pipeline_failed_calls) == 1
