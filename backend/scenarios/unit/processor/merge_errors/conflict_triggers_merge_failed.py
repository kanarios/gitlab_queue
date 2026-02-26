"""Test _process_merge triggers merge_failed on GitLabConflictError.

When the merge operation fails due to a conflict, the processor should
trigger the merge_failed transition on the state machine and return
MERGE_FAILED result.
"""

from __future__ import annotations

import vedro

from gitlab_queue.clients.gitlab import GitLabConflictError
from gitlab_queue.core.processor import ProcessingResult

from .._helpers import (
    create_mock_processor,
    create_mock_state_machine,
    create_processing_context,
    create_test_queue_item,
)


class Scenario(vedro.Scenario):
    subject = "process merge triggers merge failed on conflict error"

    def given_processor_with_merge_conflict(self):
        """
        Set up a mock processor and processing context where a GitLab merge will fail with a conflict.

        Configures:
        - self.processor: a mock processor.
        - self.queue_item: a test queue item (mr_iid=42, state="merging", expected_sha="abc123") returned by processor.queue_manager.get_queue_item.
        - processor.gitlab_client.merge_mr to raise GitLabConflictError("Merge conflict", status_code=409).
        - self.mock_sm: a mock state machine.
        - self.ctx: a processing context for mr_iid=42 using the mock state machine.
        """
        self.processor = create_mock_processor()

        self.queue_item = create_test_queue_item(mr_iid=42, state="merging", expected_sha="abc123")
        self.processor.queue_manager.get_queue_item.return_value = self.queue_item

        self.processor.gitlab_client.merge_mr.side_effect = GitLabConflictError("Merge conflict", status_code=409)

        self.mock_sm = create_mock_state_machine()
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.mock_sm)

    async def when_process_merge_is_called(self):
        """
        Execute the processor's merge handling for the prepared processing context.

        Returns:
            ProcessingResult: The processing result indicating the outcome of the merge operation.
        """
        self.result = await self.processor._process_merge(self.ctx)

    def then_result_is_merge_failed(self):
        """
        Asserts that the processing result equals ProcessingResult.MERGE_FAILED.

        Raises an AssertionError if the stored result is not ProcessingResult.MERGE_FAILED.
        """
        assert self.result == ProcessingResult.MERGE_FAILED

    def and_merge_failed_is_triggered_on_state_machine(self):
        """
        Asserts that the state machine's merge-failed trigger was awaited exactly once and that the call included an "error_message" keyword argument.

        Raises:
            AssertionError: If the trigger was not awaited exactly once or if "error_message" is not present in the trigger call kwargs.
        """
        self.mock_sm.trigger_merge_failed.assert_awaited_once()
        call_kwargs = self.mock_sm.trigger_merge_failed.call_args.kwargs
        assert "error_message" in call_kwargs
