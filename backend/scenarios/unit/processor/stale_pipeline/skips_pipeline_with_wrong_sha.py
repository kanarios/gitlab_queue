"""Test check_stale_pipeline returns SKIP for SHA mismatch.

When the queue item tracks an expected SHA and the current pipeline
has a different SHA, the pipeline is for a different commit (e.g.,
from before a rebase) and should be skipped.
"""

from __future__ import annotations

import vedro

from gitlab_queue.core.types import StaleCheckResult
from scenarios.fakes import FakeQueueManager

from .._helpers import (
    create_mock_pipeline,
    create_test_pipeline_handler,
    create_test_queue_item,
)


class Scenario(vedro.Scenario):
    subject = "check stale pipeline returns SKIP for wrong SHA"

    def given_handler_with_sha_mismatch(self):
        self.queue_manager = FakeQueueManager()
        queue_item = create_test_queue_item(
            mr_iid=42,
            state="testing",
            pipeline_id=100,
            expected_sha="abc123",
        )
        self.queue_manager.add_item(queue_item)
        self.handler = create_test_pipeline_handler(queue_manager=self.queue_manager)

        self.pipeline = create_mock_pipeline(pipeline_id=100, sha="def456", status="success")

    async def when_check_stale_pipeline_is_called(self):
        self.result = await self.handler.check_stale_pipeline(42, self.pipeline)

    def then_result_is_skip(self):
        assert self.result == StaleCheckResult.SKIP
