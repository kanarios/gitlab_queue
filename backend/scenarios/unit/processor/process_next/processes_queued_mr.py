"""Test _process_iteration picks up and processes a queued MR.

When get_next_mr returns a queue item, the processor should call _process_mr
with that item, set the current MR IID during processing, and clear it after.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import vedro

from gitlab_queue.core.processor import ProcessingResult

from .._helpers import (
    create_mock_processor,
    create_test_queue_item,
)


class Scenario(vedro.Scenario):
    subject = "process iteration calls process mr for queued item"

    def given_processor_with_mr_in_queue(self):
        self.processor = create_mock_processor()
        self.processor.queue_manager.get_stale_mrs.return_value = []

        self.queue_item = create_test_queue_item(mr_iid=42, state="queued")
        self.processor.queue_manager.get_next_mr.return_value = self.queue_item

    async def when_process_iteration_is_called(self):
        with patch.object(
            self.processor,
            "_process_mr",
            new_callable=AsyncMock,
            return_value=ProcessingResult.SUCCESS,
        ) as self.mock_process_mr:
            await self.processor._process_iteration()

    def then_get_next_mr_is_called(self):
        self.processor.queue_manager.get_next_mr.assert_awaited_once()

    def and_process_mr_is_called_with_the_queue_item(self):
        self.mock_process_mr.assert_awaited_once_with(self.queue_item)

    def and_current_mr_iid_is_cleared_after_processing(self):
        assert self.processor._current_mr_iid is None
