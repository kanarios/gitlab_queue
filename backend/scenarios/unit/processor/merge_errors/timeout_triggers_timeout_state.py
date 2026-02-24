"""Test _process_merge triggers timeout state on TimeoutError.

When the merge operation exceeds the configured timeout, the processor
should trigger the timeout transition on the state machine and return
TIMEOUT result.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import vedro

from gitlab_queue.core.processor import ProcessingResult

from .._helpers import (
    create_mock_processor,
    create_mock_state_machine,
    create_processing_context,
    create_test_queue_item,
)


class Scenario(vedro.Scenario):
    subject = "process merge triggers timeout state on TimeoutError"

    def given_processor_with_merge_timeout(self):
        self.processor = create_mock_processor()

        self.queue_item = create_test_queue_item(mr_iid=42, state="merging", expected_sha="abc123")
        self.processor.queue_manager.get_queue_item.return_value = self.queue_item

        self.mock_sm = create_mock_state_machine()
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.mock_sm)

    async def when_process_merge_is_called_with_timeout(self):
        with patch(
            "gitlab_queue.core.processor.asyncio.wait_for",
            new_callable=AsyncMock,
            side_effect=TimeoutError,
        ):
            self.result = await self.processor._process_merge(self.ctx)

    def then_result_is_timeout(self):
        assert self.result == ProcessingResult.TIMEOUT

    def and_timeout_is_triggered_on_state_machine(self):
        self.mock_sm.trigger_timeout.assert_awaited_once_with(max_wait_hours=0)
