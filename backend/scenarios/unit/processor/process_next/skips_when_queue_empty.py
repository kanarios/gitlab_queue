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
        """
        Set up self.processor as a mock processor configured to simulate an empty queue.

        Configures the processor's queue_manager so that get_next_mr returns None and get_stale_mrs returns an empty list.
        """
        self.processor = create_mock_processor()
        self.processor.queue_manager.get_next_mr.return_value = None
        self.processor.queue_manager.get_stale_mrs.return_value = []

    async def when_process_iteration_is_called(self):
        """
        Exercise the processor's _process_iteration while capturing calls to its _process_mr method with an AsyncMock stored on `self.mock_process_mr`.

        The patched mock lets subsequent test steps assert whether `_process_mr` was awaited or not.
        """
        with patch.object(
            self.processor,
            "_process_mr",
            new_callable=AsyncMock,
        ) as self.mock_process_mr:
            await self.processor._process_iteration()

    def then_get_next_mr_is_called(self):
        """
        Asserts the processor's queue manager was asked for the next MR exactly once.

        Raises:
            AssertionError: If `get_next_mr` was not awaited exactly one time.
        """
        self.processor.queue_manager.get_next_mr.assert_awaited_once()

    def and_process_mr_is_not_called(self):
        """
        Asserts that the patched _process_mr coroutine was not awaited.

        Raises an AssertionError if the coroutine was awaited.
        """
        self.mock_process_mr.assert_not_awaited()
