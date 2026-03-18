"""Test that merge_queue label is removed when MR was merged externally (e.g. Auto-merge).

When GitLab Auto-merge merges an MR:
- state=merged is returned from GitLab
- The bot must remove the merge_queue label (GitLab doesn't remove custom labels)
- This happens inside verify_mr_in_queue before trigger_mark_removed is called
"""

from __future__ import annotations

import vedro

from gitlab_queue.core.types import ProcessingResult
from scenarios.fakes import FakeStateMachine, FakeStateMachineFactory, create_mr

from .._helpers import (
    create_mock_processor,
    create_test_queue_item,
)


class Scenario(vedro.Scenario):
    subject = "MR merged externally removes queue label before mark_removed"

    def given_processor_where_mr_was_auto_merged(self):
        self.mock_sm = FakeStateMachine()
        sm_factory = FakeStateMachineFactory(state_machine=self.mock_sm)

        self.processor = create_mock_processor(state_machine_factory=sm_factory)
        self.queue_item = create_test_queue_item(mr_iid=42, state="merging")

        # MR is merged externally (e.g. GitLab Auto-merge) — still has the label
        self.processor.gitlab_client.mr_responses[42] = create_mr(iid=42, state="merged", labels=["merge_queue"])

    async def when_process_mr_is_called(self):
        self.result = await self.processor._process_mr(self.queue_item)

    def then_result_is_removed(self):
        assert self.result == ProcessingResult.REMOVED

    def and_queue_label_was_removed_via_api(self):
        assert (42, "merge_queue") in self.processor.gitlab_client.remove_label_calls

    def and_trigger_mark_removed_was_called(self):
        assert len(self.mock_sm.mark_removed_calls) == 1
        assert self.mock_sm.mark_removed_calls[0]["reason"] == "label_removed"


class ScenarioClosedDoesNotRemoveLabel(vedro.Scenario):
    subject = "MR closed (not merged) does NOT remove queue label via API"

    def given_processor_where_mr_was_closed(self):
        self.mock_sm = FakeStateMachine()
        sm_factory = FakeStateMachineFactory(state_machine=self.mock_sm)

        self.processor = create_mock_processor(state_machine_factory=sm_factory)
        self.queue_item = create_test_queue_item(mr_iid=42, state="merging")

        # MR is closed (declined), not merged
        self.processor.gitlab_client.mr_responses[42] = create_mr(iid=42, state="closed", labels=["merge_queue"])

    async def when_process_mr_is_called(self):
        self.result = await self.processor._process_mr(self.queue_item)

    def then_result_is_removed(self):
        assert self.result == ProcessingResult.REMOVED

    def and_queue_label_was_NOT_removed_via_api(self):
        assert self.processor.gitlab_client.remove_label_calls == []
