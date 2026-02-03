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
        self.processor = create_mock_processor()
        self.queue_item = create_test_queue_item(mr_iid=42, state="queued")

    async def when_process_mr_is_called(self):
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
        assert self.raised is asyncio.CancelledError
