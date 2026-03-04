"""Test _should_skip_stale_pipeline returns False when pipeline_id matches.

After job retry, the pipeline_id should NOT change (jobs are retried in-place).
_should_skip_stale_pipeline should return False when pipeline_id matches.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import vedro

from .._helpers import (
    create_mock_pipeline,
    create_mock_processor,
    create_test_queue_item,
)


class Scenario(vedro.Scenario):
    subject = "stale pipeline check returns False when pipeline_id matches (job retry preserves pipeline_id)"

    def given_processor_with_matching_pipeline_id(self):
        self.processor = create_mock_processor()

        # Queue item has pipeline_id=100 (same as current pipeline)
        self.queue_item = create_test_queue_item(
            mr_iid=42,
            state="testing",
            pipeline_id=100,
        )
        self.processor.queue_manager.get_queue_item = AsyncMock(return_value=self.queue_item)

        # Current pipeline has same id=100
        self.pipeline = create_mock_pipeline(pipeline_id=100, sha="abc123", status="running")

    async def when_should_skip_stale_pipeline_is_called(self):
        self.result = await self.processor._pipeline_handler.should_skip_stale_pipeline(42, self.pipeline)

    def then_result_is_false(self):
        assert self.result is False
