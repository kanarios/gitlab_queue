"""Test _process_mr propagates CancelledError.

When state_machine_factory raises asyncio.CancelledError during
MR processing, the error must propagate up without being caught, so
that asyncio task cancellation works correctly.
"""

from __future__ import annotations

import asyncio

import vedro

from .._helpers import (
    create_mock_processor,
    create_test_queue_item,
)


async def _cancelling_factory(*args, **kwargs):
    raise asyncio.CancelledError()


class Scenario(vedro.Scenario):
    subject = "process mr propagates CancelledError"

    def given_processor_with_queued_mr(self):
        self.processor = create_mock_processor(state_machine_factory=_cancelling_factory)
        self.queue_item = create_test_queue_item(mr_iid=42, state="queued")

    async def when_process_mr_is_called(self):
        self.raised = None
        try:
            await self.processor._process_mr(self.queue_item)
        except asyncio.CancelledError:
            self.raised = asyncio.CancelledError

    def then_cancelled_error_is_raised(self):
        assert self.raised is asyncio.CancelledError
