"""Test that externally merged MR triggers mark_removed with external_merge reason."""

from __future__ import annotations

import vedro

from gitlab_queue.core.types import ProcessingResult
from scenarios.fakes import FakeStateMachine, FakeStateMachineFactory, create_mr

from .._helpers import create_mock_processor, create_test_queue_item


class Scenario(vedro.Scenario):
    subject = "externally merged MR triggers mark_removed with external_merge reason"

    def given_processor_where_mr_was_merged_externally(self):
        self.mock_sm = FakeStateMachine()
        sm_factory = FakeStateMachineFactory(state_machine=self.mock_sm)

        self.processor = create_mock_processor(state_machine_factory=sm_factory)
        self.queue_item = create_test_queue_item(mr_iid=42, state="merging")

        self.processor.gitlab_client.mr_responses[42] = create_mr(iid=42, state="merged", labels=["merge_queue"])

    async def when_process_mr_is_called(self):
        self.result = await self.processor._process_mr(self.queue_item)

    def then_result_is_removed(self):
        assert self.result == ProcessingResult.REMOVED

    def then_reason_is_external_merge(self):
        assert len(self.mock_sm.mark_removed_calls) == 1
        assert self.mock_sm.mark_removed_calls[0]["reason"] == "external_merge"
