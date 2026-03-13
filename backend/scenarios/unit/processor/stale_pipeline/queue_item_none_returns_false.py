"""Test check_stale_pipeline returns OK when queue_item is None.

When get_queue_item returns None, there is no stale pipeline to detect.
"""

from __future__ import annotations

import vedro

from gitlab_queue.core.types import StaleCheckResult

from .._helpers import (
    create_mock_pipeline,
    create_test_pipeline_handler,
)


class Scenario(vedro.Scenario):
    subject = "check stale pipeline returns OK when queue item is None"

    def given_handler_with_no_queue_item(self):
        self.handler = create_test_pipeline_handler()
        self.pipeline = create_mock_pipeline(pipeline_id=100, sha="abc123", status="running")

    async def when_check_stale_pipeline_is_called(self):
        self.result = await self.handler.check_stale_pipeline(42, self.pipeline)

    def then_result_is_ok(self):
        assert self.result == StaleCheckResult.OK
