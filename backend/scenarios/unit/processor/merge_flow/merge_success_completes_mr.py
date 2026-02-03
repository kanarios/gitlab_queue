"""Test _process_merge triggers merge_success and returns SUCCESS on successful merge.

When gitlab_client.merge_mr completes successfully, the processor should
trigger the merge_success transition on the state machine and return
ProcessingResult.SUCCESS.

Covers lines 1164-1166 in _process_merge: the happy-path branch after
asyncio.wait_for completes, calling trigger_merge_success.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import vedro

from gitlab_queue.core.processor import ProcessingResult

from .._helpers import (
    create_mock_processor,
    create_mock_state_machine,
    create_processing_context,
    create_test_queue_item,
)


class Scenario(vedro.Scenario):
    subject = "process merge triggers merge success and returns SUCCESS on successful merge"

    def given_processor_with_successful_merge(self):
        self.processor = create_mock_processor()

        # Queue item with an expected SHA to test the race-condition guard
        self.queue_item = create_test_queue_item(mr_iid=42, state="merging", expected_sha="sha_merge_ok")
        self.processor.queue_manager.get_queue_item.return_value = self.queue_item

        # Simulate a merged MR returned by merge_mr
        self.merged_mr = MagicMock()
        self.merged_mr.state = "merged"
        self.processor.gitlab_client.merge_mr = AsyncMock(return_value=self.merged_mr)

        self.mock_sm = create_mock_state_machine()
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.mock_sm)

    async def when_process_merge_is_called(self):
        self.result = await self.processor._process_merge(self.ctx)

    def then_result_is_success(self):
        assert self.result == ProcessingResult.SUCCESS

    def and_merge_success_is_triggered_on_state_machine(self):
        self.mock_sm.trigger_merge_success.assert_called_once()

    def and_merge_mr_is_called_with_correct_sha(self):
        self.processor.gitlab_client.merge_mr.assert_called_once_with(42, expected_sha="sha_merge_ok")

    def and_no_failure_transitions_are_triggered(self):
        self.mock_sm.trigger_merge_failed.assert_not_called()
        self.mock_sm.trigger_timeout.assert_not_called()
