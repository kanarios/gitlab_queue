"""Test _check_stale_mrs sends warning for stale MR.

When an MR has been in the queue longer than the warning threshold and
has not yet been warned, a stale warning notification should be sent
and the warning flag should be marked.
"""

from __future__ import annotations

import vedro

from scenarios.fakes import FakeStateMachine, FakeStateMachineFactory

from .._helpers import (
    create_mock_processor,
    create_test_queue_item,
)


class Scenario(vedro.Scenario):
    subject = "check stale mrs sends warning for unwarned stale MR"

    def given_processor_with_stale_unwarned_mr(self):
        self.fake_sm = FakeStateMachine()
        self.sm_factory = FakeStateMachineFactory(state_machine=self.fake_sm)
        self.processor = create_mock_processor(state_machine_factory=self.sm_factory)

        self.stale_item = create_test_queue_item(mr_iid=42, state="queued", stale_warning_sent=False)
        self.processor.queue_manager.add_item(self.stale_item)

    async def when_check_stale_mrs_is_called(self):
        await self.processor._check_stale_mrs()

    def then_stale_warning_is_sent(self):
        assert self.fake_sm.stale_warning_calls == [{"warning_hours": 24}]

    def and_warning_flag_is_marked(self):
        assert self.processor.queue_manager.stale_warning_calls == [42]
