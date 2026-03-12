"""Test should_skip_stale_pipeline skips newer pipeline when expected_sha is None.

When the queue item has no expected_sha set, we cannot verify that
the new pipeline is for the correct commit, so we fall back to
the existing behavior of skipping on pipeline_id mismatch.
"""

from __future__ import annotations

import vedro

from .._helpers import (
    create_mock_pipeline,
    create_mock_processor,
    create_test_queue_item,
)


class Scenario(vedro.Scenario):
    subject = "should skip stale pipeline skips newer pipeline when expected SHA is None"

    def given_processor_with_no_expected_sha(self):
        self.processor = create_mock_processor()

        self.queue_item = create_test_queue_item(
            mr_iid=42,
            state="testing",
            pipeline_id=100,
            expected_sha=None,
        )
        self.processor.queue_manager.add_item(self.queue_item)

        self.pipeline = create_mock_pipeline(
            pipeline_id=200,
            sha="abc12345",
            status="running",
        )

    async def when_should_skip_stale_pipeline_is_called(self):
        self.result = await self.processor._pipeline_handler.should_skip_stale_pipeline(
            42,
            self.pipeline,
        )

    def then_pipeline_should_be_skipped(self):
        assert self.result is True
