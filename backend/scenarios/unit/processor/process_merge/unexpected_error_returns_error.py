"""Test _process_mr returns ERROR on unexpected exception.

When create_state_machine_for_mr raises an unexpected RuntimeError,
_process_mr should catch it and return ProcessingResult.ERROR instead
of letting the exception propagate and crash the processing loop.
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
    subject = "process mr returns error on unexpected exception"

    def given_processor_with_create_state_machine_raising_runtime_error(self):
        """
        Set up a mock processor and a queued merge-request queue item on self.

        Creates:
        - self.processor: a mock processor for the test.
        - self.queue_item: a queue item representing MR with iid 42 and state "queued".
        """
        self.processor = create_mock_processor()
        self.queue_item = create_test_queue_item(mr_iid=42, state="queued")

    async def when_process_mr_is_called(self):
        with patch(
            "gitlab_queue.core.processor.create_state_machine_for_mr",
            new_callable=AsyncMock,
            side_effect=RuntimeError("boom"),
        ):
            self.result = await self.processor._process_mr(self.queue_item)

    def then_result_is_error(self):
        """
        Asserts that processing the merge request produced an error result.

        Raises:
            AssertionError: If the stored result is not ProcessingResult.ERROR.
        """
        assert self.result == ProcessingResult.ERROR
