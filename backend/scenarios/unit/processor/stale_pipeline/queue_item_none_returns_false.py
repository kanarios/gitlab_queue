"""Test _should_skip_stale_pipeline returns False when queue_item is None.

Line 884: when get_queue_item returns None, return False (no stale pipeline to detect).
"""

from __future__ import annotations

import vedro

from .._helpers import (
    create_mock_pipeline,
    create_mock_processor,
)


class Scenario(vedro.Scenario):
    subject = "should_skip_stale_pipeline returns False when queue item is None"

    def given_processor_with_no_queue_item(self):
        self.processor = create_mock_processor()

        # Queue item is not found (empty queue — get_queue_item returns None)

        self.pipeline = create_mock_pipeline(pipeline_id=100, sha="abc123", status="running")

    async def when_should_skip_stale_pipeline_is_called(self):
        self.result = await self.processor._pipeline_handler.should_skip_stale_pipeline(42, self.pipeline)

    def then_result_is_false(self):
        assert self.result is False
