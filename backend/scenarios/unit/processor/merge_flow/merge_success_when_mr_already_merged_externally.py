"""Test processor handles MR already merged externally as SUCCESS.

When gitlab_client.merge_mr returns an MR with state="merged" (because
the MR was merged by another user or auto-merge), the processor should
trigger merge_success and return ProcessingResult.SUCCESS — not an error.
"""

from __future__ import annotations

import vedro

from gitlab_queue.core.processor import ProcessingResult
from scenarios.fakes import create_mr

from .._helpers import (
    create_mock_processor,
    create_mock_state_machine,
    create_processing_context,
    create_test_queue_item,
)


class Scenario(vedro.Scenario):
    subject = "processor treats externally merged MR as SUCCESS"

    def given_processor_with_externally_merged_mr(self):
        self.processor = create_mock_processor()

        self.queue_item = create_test_queue_item(mr_iid=42, state="merging", expected_sha="abc123")
        self.processor.queue_manager.add_item(self.queue_item)

        self.merged_mr = create_mr(iid=42, state="merged")
        self.processor.gitlab_client.merge_result = self.merged_mr

        self.mock_sm = create_mock_state_machine()
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.mock_sm)

    async def when_process_merge_is_called(self):
        self.result = await self.processor._process_merge(self.ctx)

    def then_result_is_success(self):
        assert self.result == ProcessingResult.SUCCESS

    def and_merge_success_is_triggered(self):
        assert len(self.mock_sm.merge_success_calls) == 1

    def and_no_failure_transitions(self):
        assert self.mock_sm.merge_failed_calls == []
        assert self.mock_sm.timeout_calls == []
