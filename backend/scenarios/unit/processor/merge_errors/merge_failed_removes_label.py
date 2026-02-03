"""Test _process_merge triggers merge_failed which initiates label removal.

When the merge operation fails due to a conflict error, the processor
should call trigger_merge_failed on the state machine. The state machine's
on_enter_failed hook is responsible for removing the queue label via the
notifier. This test verifies that trigger_merge_failed is invoked, which
is the precondition for label removal.
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
    subject = "merge failed triggers state machine which removes queue label"

    def given_processor_with_merge_conflict_and_notifier(self):
        self.processor = create_mock_processor()

        self.queue_item = create_test_queue_item(mr_iid=42, state="merging", expected_sha="abc123")
        self.processor.queue_manager.get_queue_item.return_value = self.queue_item

        self.processor.gitlab_client.merge_mr.side_effect = GitLabConflictError(
            "Merge conflict detected", status_code=409
        )

        self.mock_sm = create_mock_state_machine()
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.mock_sm)

    async def when_process_merge_encounters_conflict(self):
        self.result = await self.processor._process_merge(self.ctx)

    def then_result_is_merge_failed(self):
        assert self.result == ProcessingResult.MERGE_FAILED

    def and_trigger_merge_failed_is_called_on_state_machine(self):
        self.mock_sm.trigger_merge_failed.assert_called_once()

    def and_error_message_is_passed_to_state_machine(self):
        call_kwargs = self.mock_sm.trigger_merge_failed.call_args.kwargs
        assert "error_message" in call_kwargs
        assert "Merge conflict" in call_kwargs["error_message"]

    def and_merge_success_is_not_triggered(self):
        self.mock_sm.trigger_merge_success.assert_not_called()
