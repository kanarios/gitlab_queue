"""Test _should_skip_stale_pipeline returns True for pipeline_id mismatch.

When the queue item tracks a specific pipeline_id and the current
pipeline has a different ID, the pipeline is stale (from before a
rebase/retry) and should be skipped.
"""

from __future__ import annotations

import vedro

from .._helpers import (
    create_mock_pipeline,
    create_mock_processor,
    create_test_queue_item,
)


class Scenario(vedro.Scenario):
    subject = "should skip stale pipeline returns True for wrong pipeline id"

    def given_processor_with_pipeline_id_mismatch(self):
        """
        Prepare a processor and mocks where the stored queue item's pipeline_id differs from the current pipeline's id.

        Creates a mock processor, a test queue item with mr_iid=42, state="testing", pipeline_id=100 and expected_sha="abc123", configures the processor's queue_manager.get_queue_item to return that queue item, and creates a mock pipeline with pipeline_id=200 and sha="abc123". Sets self.processor, self.queue_item and self.pipeline.
        """
        self.processor = create_mock_processor()

        self.queue_item = create_test_queue_item(
            mr_iid=42,
            state="testing",
            pipeline_id=100,
            expected_sha="abc123",
        )
        self.processor.queue_manager.get_queue_item.return_value = self.queue_item

        self.pipeline = create_mock_pipeline(pipeline_id=200, sha="abc123", status="success")

    async def when_should_skip_stale_pipeline_is_called(self):
        """
        Invoke the method under test to determine whether the prepared pipeline should be considered stale and store the outcome.

        Sets self.result to `True` if the pipeline should be skipped (stale) for MR IID 42, `False` otherwise.
        """
        self.result = await self.processor._should_skip_stale_pipeline(42, self.pipeline)

    def then_pipeline_should_be_skipped(self):
        """
        Verify the pipeline is identified as stale and should be skipped.

        Asserts that `self.result` is `True`.
        """
        assert self.result is True
