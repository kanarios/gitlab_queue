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
        self.processor = create_mock_processor()

        self.queue_item = create_test_queue_item(mr_iid=42, state="merging", expected_sha="abc123")
        self.processor.queue_manager.get_queue_item.return_value = self.queue_item

        self.processor.gitlab_client.merge_mr.side_effect = GitLabAPIError("Internal server error", status_code=500)

        self.mock_sm = create_mock_state_machine()
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.mock_sm)

    async def when_process_merge_is_called(self):
        self.result = await self.processor._process_merge(self.ctx)

    def then_result_is_merge_failed(self):
        assert self.result == ProcessingResult.MERGE_FAILED

    def and_merge_failed_is_triggered_on_state_machine(self):
        self.mock_sm.trigger_merge_failed.assert_called_once()
        call_kwargs = self.mock_sm.trigger_merge_failed.call_args.kwargs
        assert "error_message" in call_kwargs
