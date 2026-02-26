"""Test _process_mr propagates CancelledError.

When create_state_machine_for_mr raises asyncio.CancelledError during
MR processing, the error must propagate up without being caught, so
that asyncio task cancellation works correctly.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import vedro

from .._helpers import (
    create_mock_processor,
    create_test_queue_item,
)


class Scenario(vedro.Scenario):
    subject = "process mr propagates CancelledError"

    def given_processor_with_create_state_machine_raising_cancelled(self):
        """
        Prepare test fixtures: set self.processor to a mock processor and self.queue_item to a queued merge request item.

        Sets:
            self.processor: a mock processor instance.
            self.queue_item: a test queue item representing MR IID 42 in the "queued" state.
        """
        self.processor = create_mock_processor()
        self.queue_item = create_test_queue_item(mr_iid=42, state="queued")

    async def when_process_mr_is_called(self):
        """
        Invoke the processor's _process_mr while simulating a cancelled state machine and record whether asyncio.CancelledError propagates.

        Patches gitlab_queue.core.processor.create_state_machine_for_mr to raise asyncio.CancelledError, awaits self.processor._process_mr(self.queue_item), and sets self.raised to asyncio.CancelledError if the exception is propagated to the caller.
        """
        self.raised = None
        with patch(
            "gitlab_queue.core.processor.create_state_machine_for_mr",
            new_callable=AsyncMock,
            side_effect=asyncio.CancelledError(),
        ):
            try:
                await self.processor._process_mr(self.queue_item)
            except asyncio.CancelledError:
                self.raised = asyncio.CancelledError

    def then_cancelled_error_is_raised(self):
        """
        Asserts that the awaited operation raised asyncio.CancelledError.

        Raises an AssertionError if the recorded exception is not asyncio.CancelledError.
        """
        assert self.raised is asyncio.CancelledError
