"""Test _check_stale_mrs skips already warned MR.

When an MR already has stale_warning_sent=True, no additional warning
should be sent and mark_stale_warning_sent should not be called again.
"""

from __future__ import annotations

import vedro

from scenarios.fakes import FakeStateMachineFactory

from .._helpers import create_mock_processor, create_test_queue_item


class Scenario(vedro.Scenario):
    subject = "check stale mrs skips already warned MR"

    def given_processor_with_already_warned_stale_mr(self):
        self.sm_factory = FakeStateMachineFactory()
        self.processor = create_mock_processor(state_machine_factory=self.sm_factory)

        # stale_warning_sent=True means get_stale_mrs won't return it
        self.stale_item = create_test_queue_item(mr_iid=42, state="queued", stale_warning_sent=True)
        self.processor.queue_manager.add_item(self.stale_item)

    async def when_check_stale_mrs_is_called(self):
        await self.processor._check_stale_mrs()

    def then_state_machine_is_not_created(self):
        assert self.sm_factory.calls == []

    def and_warning_flag_is_not_marked(self):
        assert self.processor.queue_manager.stale_warning_calls == []
