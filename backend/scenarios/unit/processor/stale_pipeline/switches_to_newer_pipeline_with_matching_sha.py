"""Test check_stale_pipeline returns SWITCHED for newer pipeline with matching SHA.

When GitLab creates a new pipeline on the same commit after rebase,
the method should signal that the caller must switch to tracking it.
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
    subject = "check stale pipeline returns SWITCHED for newer pipeline with matching SHA"

    def given_handler_with_newer_pipeline_matching_sha(self):
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
            sha="abc12345",
            status="running",
        )

    async def when_check_stale_pipeline_is_called(self):
        self.result = await self.handler.check_stale_pipeline(42, self.pipeline)

    def then_result_is_switched(self):
        assert self.result == StaleCheckResult.SWITCHED

    def then_no_side_effects_on_queue(self):
        assert self.queue_manager.update_state_calls == []
