"""Test _check_stale_mrs swallows exception from stale warning.

When state_machine_factory raises an exception during stale MR
check, the error should be caught and logged without propagating,
allowing the processor to continue checking other stale MRs.
"""

from __future__ import annotations

import vedro

from .._helpers import (
    create_mock_processor,
    create_test_queue_item,
)


class Scenario(vedro.Scenario):
    subject = "check stale mrs swallows exception from stale warning"

    def given_processor_with_stale_mr_and_failing_state_machine(self):
        self.factory_calls: list[int] = []

        async def raising_factory(*args, **kwargs):
            self.factory_calls.append(kwargs.get("mr_iid", args[0] if args else 0))
            raise Exception("State machine creation failed")

        self.processor = create_mock_processor(state_machine_factory=raising_factory)

        self.stale_item = create_test_queue_item(mr_iid=42, state="queued", stale_warning_sent=False)
        self.processor.queue_manager.add_item(self.stale_item)

    async def when_check_stale_mrs_is_called(self):
        self.raised = None
        try:
            await self.processor._check_stale_mrs()
        except Exception as exc:
            self.raised = exc

    def then_no_error_is_raised(self):
        assert self.raised is None

    def and_factory_was_invoked(self):
        assert self.factory_calls == [42]

    def and_mark_stale_warning_sent_is_not_called(self):
        assert self.processor.queue_manager.stale_warning_calls == []
