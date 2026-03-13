"""Test check_stale_pipeline returns SKIP for newer pipeline with wrong SHA.

When a newer pipeline exists but its SHA does not match the expected one,
the pipeline is for a different commit and should be skipped.
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
    subject = "check stale pipeline returns SKIP for newer pipeline with wrong SHA (status='{status}')"

    @params("running")
    @params("success")
    @params("failed")
    @params("canceled")
    @params("pending")
    def __init__(self, status: str):
        self.status = status

    def given_handler_with_newer_pipeline_wrong_sha(self):
        self.queue_manager = FakeQueueManager()
        queue_item = create_test_queue_item(
            mr_iid=42,
            state="testing",
            pipeline_id=100,
            expected_sha="abc12345",
        )
        self.queue_manager.add_item(queue_item)
        self.handler = create_test_pipeline_handler(queue_manager=self.queue_manager)

        self.pipeline = create_mock_pipeline(
            pipeline_id=200,
            sha="def67890",
            status=self.status,
        )

    async def when_check_stale_pipeline_is_called(self):
        self.result = await self.handler.check_stale_pipeline(42, self.pipeline)

    def then_result_is_skip(self):
        assert self.result == StaleCheckResult.SKIP
