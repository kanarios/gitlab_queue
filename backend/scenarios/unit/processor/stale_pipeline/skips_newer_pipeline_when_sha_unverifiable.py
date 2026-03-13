"""Test check_stale_pipeline returns SKIP when SHA cannot be verified.

When there is a pipeline_id mismatch and either expected_sha or pipeline sha
is None, we cannot confirm the newer pipeline is for the correct commit,
so it should be skipped.
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
    subject = (
        "check stale pipeline returns SKIP when SHA unverifiable (expected={expected_sha}, pipeline={pipeline_sha})"
    )

    @params(None, "abc12345")
    @params("abc12345", None)
    def __init__(self, expected_sha: str | None, pipeline_sha: str | None):
        self.expected_sha = expected_sha
        self.pipeline_sha = pipeline_sha

    def given_handler_with_unverifiable_sha(self):
        self.queue_manager = FakeQueueManager()
        queue_item = create_test_queue_item(
            mr_iid=42,
            state="testing",
            pipeline_id=100,
            expected_sha=self.expected_sha,
        )
        self.queue_manager.add_item(queue_item)
        self.handler = create_test_pipeline_handler(queue_manager=self.queue_manager)

        self.pipeline = create_mock_pipeline(
            pipeline_id=200,
            sha=self.pipeline_sha,
            status="running",
        )

    async def when_check_stale_pipeline_is_called(self):
        self.result = await self.handler.check_stale_pipeline(42, self.pipeline)

    def then_result_is_skip(self):
        assert self.result == StaleCheckResult.SKIP
