"""Test _should_skip_stale_pipeline returns True for SHA mismatch.

When the queue item tracks an expected SHA and the current pipeline
has a different SHA, the pipeline is for a different commit (e.g.,
from before a rebase) and should be skipped.
"""

from __future__ import annotations

import vedro

from .._helpers import (
    create_mock_pipeline,
    create_mock_processor,
    create_test_queue_item,
)


class Scenario(vedro.Scenario):
    subject = "should skip stale pipeline returns True for wrong SHA"

    def given_processor_with_sha_mismatch(self):
        self.processor = create_mock_processor()

        self.queue_item = create_test_queue_item(
            mr_iid=42,
            state="testing",
            pipeline_id=100,
            expected_sha="abc123",
        )
        self.processor.queue_manager.get_queue_item.return_value = self.queue_item

        self.pipeline = create_mock_pipeline(pipeline_id=100, sha="def456", status="success")

    async def when_should_skip_stale_pipeline_is_called(self):
        """
        Call processor._should_skip_stale_pipeline with MR IID 42 and the scenario pipeline, and store the call's outcome on self.result.
        """
        self.result = await self.processor._should_skip_stale_pipeline(42, self.pipeline)

    def then_pipeline_should_be_skipped(self):
        assert self.result is True
