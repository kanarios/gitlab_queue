"""Test _process_mr removes MR when _verify_mr_in_queue returns False.

When an MR no longer has the queue label, the processor should call
trigger_mark_removed and return ProcessingResult.REMOVED.
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
    subject = "process mr removes MR when verify returns False"

    def given_processor_where_mr_label_was_removed(self):
        self.mock_sm = FakeStateMachine()
        sm_factory = FakeStateMachineFactory(state_machine=self.mock_sm)

        self.processor = create_mock_processor(state_machine_factory=sm_factory)
        self.queue_item = create_test_queue_item(mr_iid=42, state="queued")

        # MR without queue label so _verify_mr_in_queue returns False
        self.processor.gitlab_client.mr_responses[42] = create_mr(iid=42, state="opened", labels=[])

    async def when_process_mr_is_called_with_label_removed(self):
        self.result = await self.processor._process_mr(self.queue_item)

    def then_result_is_removed(self):
        assert self.result == ProcessingResult.REMOVED

    def and_trigger_mark_removed_was_called(self):
        assert len(self.mock_sm.mark_removed_calls) == 1
        assert self.mock_sm.mark_removed_calls[0]["reason"] == "label_removed"
