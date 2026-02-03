"""Test _process_iteration returns early when queue is empty.

When get_next_mr returns None, the processor should log that the queue
is empty and return without calling _process_mr.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import vedro

from .._helpers import create_mock_processor


class Scenario(vedro.Scenario):
    subject = "process iteration returns early when queue is empty"

    def given_processor_with_empty_queue(self):
        self.processor = create_mock_processor()
        self.processor.queue_manager.get_next_mr.return_value = None
        self.processor.queue_manager.get_stale_mrs.return_value = []

    async def when_process_iteration_is_called(self):
        with patch.object(
            self.processor,
            "_process_mr",
            new_callable=AsyncMock,
        ) as self.mock_process_mr:
            await self.processor._process_iteration()

    def then_get_next_mr_is_called(self):
        self.processor.queue_manager.get_next_mr.assert_called_once()

    def and_process_mr_is_not_called(self):
        self.mock_process_mr.assert_not_called()
