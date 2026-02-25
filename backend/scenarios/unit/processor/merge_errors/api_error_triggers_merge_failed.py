"""Test _process_merge triggers merge_failed on GitLabAPIError.

When the merge operation fails due to a generic GitLab API error,
the processor should trigger the merge_failed transition on the
state machine and return MERGE_FAILED result.
"""

from __future__ import annotations

import vedro

from gitlab_queue.clients.gitlab import GitLabAPIError
from gitlab_queue.core.processor import ProcessingResult

from .._helpers import (
    create_mock_processor,
    create_mock_state_machine,
    create_processing_context,
    create_test_queue_item,
)


class Scenario(vedro.Scenario):
    subject = "process merge triggers merge failed on API error"

    def given_processor_with_merge_api_error(self):
        """
        Prepare test fixtures: create a mock processor configured to raise a GitLabAPIError when merging, a test queue item in the "merging" state, a mock state machine, and a processing context stored on the instance.
        
        The created attributes on self are:
        - processor: mock processor whose gitlab_client.merge_mr raises GitLabAPIError(status_code=500)
        - queue_item: test queue item with mr_iid=42, state="merging", expected_sha="abc123"
        - mock_sm: mock state machine
        - ctx: processing context for mr_iid=42 using the mock state machine
        """
        self.processor = create_mock_processor()

        self.queue_item = create_test_queue_item(mr_iid=42, state="merging", expected_sha="abc123")
        self.processor.queue_manager.get_queue_item.return_value = self.queue_item

        self.processor.gitlab_client.merge_mr.side_effect = GitLabAPIError("Internal server error", status_code=500)

        self.mock_sm = create_mock_state_machine()
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.mock_sm)

    async def when_process_merge_is_called(self):
        """
        Invoke the processor's merge handling with the prepared context and store the outcome.
        
        This awaits the processor's _process_merge called with self.ctx and assigns the returned ProcessingResult to self.result.
        """
        self.result = await self.processor._process_merge(self.ctx)

    def then_result_is_merge_failed(self):
        """
        Assert that the processing result indicates a merge failure.
        
        Raises:
            AssertionError: If the stored result is not ProcessingResult.MERGE_FAILED.
        """
        assert self.result == ProcessingResult.MERGE_FAILED

    def and_merge_failed_is_triggered_on_state_machine(self):
        """
        Verifies that the state's merge_failed transition was triggered exactly once and that the call included an 'error_message' keyword.
        
        This assertion ensures the state machine's trigger_merge_failed coroutine was awaited once and that the awaited call supplied an 'error_message' keyword argument.
        """
        self.mock_sm.trigger_merge_failed.assert_awaited_once()
        call_kwargs = self.mock_sm.trigger_merge_failed.call_args.kwargs
        assert "error_message" in call_kwargs
