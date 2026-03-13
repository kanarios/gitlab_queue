"""Test check_stale_pipeline returns OK when pipeline_id matches.

When the current pipeline has the same id as tracked in the queue,
it is the expected pipeline regardless of expected_sha state.
"""

from __future__ import annotations

import vedro
from vedro import params

from gitlab_queue.core.types import StaleCheckResult
from scenarios.fakes import FakeQueueManager

from .._helpers import (
    create_mock_pipeline,
    create_test_pipeline_handler,
    create_test_queue_item,
)


class Scenario(vedro.Scenario):
    subject = "check stale pipeline returns OK when pipeline_id matches (expected_sha={expected_sha})"

    @params("abc123", "abc123")
    @params(None, "abc123")
    def __init__(self, expected_sha: str | None, pipeline_sha: str):
        self.expected_sha = expected_sha
        self.pipeline_sha = pipeline_sha

    def given_handler_with_matching_pipeline_id(self):
        self.queue_manager = FakeQueueManager()
        queue_item = create_test_queue_item(
            mr_iid=42,
            state="testing",
            pipeline_id=100,
            expected_sha=self.expected_sha,
        )
        self.queue_manager.add_item(queue_item)
        self.handler = create_test_pipeline_handler(queue_manager=self.queue_manager)

        self.pipeline = create_mock_pipeline(pipeline_id=100, sha=self.pipeline_sha, status="running")

    async def when_check_stale_pipeline_is_called(self):
        self.result = await self.handler.check_stale_pipeline(42, self.pipeline)

    def then_result_is_ok(self):
        assert self.result == StaleCheckResult.OK
